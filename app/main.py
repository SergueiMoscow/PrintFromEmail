import logging
import shutil
import signal
import tempfile
import time
from pathlib import Path

from app.allowlist import is_allowed, load_allowlist
from app.config import Settings
from app.converter import get_converter
from app.interfaces import AttachmentStorage, Converter, MailSource, Printer, StateStore
from app.mailbox import ImapMailSource
from app.models import Attachment, Message, Orientation, PrintOptions, PrintResult, PrintStatus, Sides
from app.parser import parse_print_options
from app.printer import CupsPrinter
from app.state import SqliteStateStore
from app.storage import LocalAttachmentStorage

logger = logging.getLogger(__name__)


def _default_options(settings: Settings) -> PrintOptions:
    if settings.print_default_sides == 1:
        sides = Sides.ONE_SIDED
    elif settings.print_default_edge == "s":
        sides = Sides.TWO_SIDED_SHORT_EDGE
    else:
        sides = Sides.TWO_SIDED_LONG_EDGE

    return PrintOptions(
        orientation=Orientation(settings.print_default_orientation),
        sides=sides,
    )


def _filter_attachments(
    attachments: list[Attachment],
    allowed_extensions: set[str],
    max_bytes: int,
    mode: str,
) -> list[Attachment]:
    filtered = [
        att
        for att in attachments
        if Path(att.filename).suffix.lstrip(".").lower() in allowed_extensions
        and len(att.data) <= max_bytes
    ]
    if mode == "FIRST":
        return filtered[:1]
    return filtered


def _process_message(
    message: Message,
    defaults: PrintOptions,
    settings: Settings,
    printer: Printer,
    storage: AttachmentStorage,
    state: StateStore,
) -> PrintResult:
    options = parse_print_options(message.body_text, defaults)
    attachments = _filter_attachments(
        message.attachments,
        settings.allowed_extensions_set,
        settings.max_attachment_bytes,
        settings.print_attachments,
    )

    if not attachments:
        logger.info("No printable attachments in message %s", message.message_id)
        result = PrintResult(
            message_id=message.message_id,
            sender=message.sender,
            subject=message.subject,
            status=PrintStatus.REJECTED,
            error="No printable attachments found",
        )
        state.record(result)
        return result

    saved_files: list[str] = []
    errors: list[str] = []
    tmpdir = Path(tempfile.mkdtemp())

    try:
        for att in attachments:
            try:
                ext = Path(att.filename).suffix.lstrip(".").lower()
                tmp_file = tmpdir / att.filename
                tmp_file.write_bytes(att.data)

                converter = get_converter(ext)
                pdf_path = converter.to_pdf(tmp_file)

                printer.print(pdf_path, options)

                filename = storage.save(att, message.message_id)
                saved_files.append(filename)
                logger.info("Printed and saved: %s", filename)

            except Exception as exc:
                logger.error("Failed to process attachment %s: %s", att.filename, exc)
                errors.append(f"{att.filename}: {exc}")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    if errors and not saved_files:
        status = PrintStatus.ERROR
        error_msg = "; ".join(errors)
    elif errors:
        status = PrintStatus.PARTIAL
        error_msg = "; ".join(errors)
    else:
        status = PrintStatus.PRINTED
        error_msg = None

    result = PrintResult(
        message_id=message.message_id,
        sender=message.sender,
        subject=message.subject,
        status=status,
        saved_files=saved_files,
        error=error_msg,
    )
    state.record(result)
    return result


class Agent:
    def __init__(
        self,
        mail_source: MailSource,
        printer: Printer,
        storage: AttachmentStorage,
        state: StateStore,
        settings: Settings,
    ) -> None:
        self._mail = mail_source
        self._printer = printer
        self._storage = storage
        self._state = state
        self._settings = settings
        self._running = True

    def stop(self) -> None:
        self._running = False

    def run(self) -> None:
        defaults = _default_options(self._settings)
        allowlist = load_allowlist(
            self._settings.allowed_senders,
            self._settings.allowed_senders_file,
        )
        logger.info("Allowlist loaded (%d addresses)", len(allowlist))
        logger.info("Starting poll loop (interval=%ds)", self._settings.poll_interval)

        while self._running:
            try:
                self._tick(defaults, allowlist)
            except Exception as exc:
                logger.error("Poll iteration failed: %s", exc)

            for _ in range(self._settings.poll_interval):
                if not self._running:
                    break
                time.sleep(1)

        logger.info("Agent stopped")

    def _tick(self, defaults: PrintOptions, allowlist: set[str]) -> None:
        logger.debug("Fetching messages…")
        messages = self._mail.fetch()
        logger.info("Fetched %d unseen message(s)", len(messages))

        for message in messages:
            try:
                self._handle_message(message, defaults, allowlist)
            except Exception as exc:
                logger.error("Unhandled error for message %s: %s", message.message_id, exc)

    def _handle_message(
        self, message: Message, defaults: PrintOptions, allowlist: set[str]
    ) -> None:
        if not is_allowed(message.sender, allowlist):
            logger.warning("Rejected sender: %s (message %s)", message.sender, message.message_id)
            return

        if self._state.is_processed(message.message_id):
            logger.debug("Already processed: %s", message.message_id)
            return

        logger.info(
            "Processing message %s from %s: %r",
            message.message_id, message.sender, message.subject,
        )

        result = _process_message(
            message=message,
            defaults=defaults,
            settings=self._settings,
            printer=self._printer,
            storage=self._storage,
            state=self._state,
        )

        if (
            result.status == PrintStatus.PRINTED
            and self._settings.delete_from_mailbox
        ):
            try:
                self._mail.delete(message.message_id)
            except Exception as exc:
                logger.error("Failed to delete message %s: %s", message.message_id, exc)


def main() -> None:
    settings = Settings()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    mail_source = ImapMailSource(
        host=settings.imap_host,
        port=settings.imap_port,
        ssl=settings.imap_ssl,
        user=settings.imap_user,
        password=settings.imap_password,
        folder=settings.imap_folder,
    )
    printer = CupsPrinter(settings.printer_name)
    storage = LocalAttachmentStorage(settings.printed_dir)
    state = SqliteStateStore(settings.db_path)

    agent = Agent(
        mail_source=mail_source,
        printer=printer,
        storage=storage,
        state=state,
        settings=settings,
    )

    def _handle_signal(signum: int, frame: object) -> None:
        logger.info("Received signal %d, shutting down…", signum)
        agent.stop()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    agent.run()


if __name__ == "__main__":
    main()
