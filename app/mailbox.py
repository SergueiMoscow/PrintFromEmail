import logging

from imap_tools import AND, MailBox, MailBoxUnencrypted, MailMessage

from app.models import Attachment, Message

logger = logging.getLogger(__name__)


_SOCKET_TIMEOUT = 30  # seconds


def _make_mailbox(host: str, port: int, ssl: bool) -> MailBox | MailBoxUnencrypted:
    if ssl:
        return MailBox(host, port=port, timeout=_SOCKET_TIMEOUT)
    return MailBoxUnencrypted(host, port=port, timeout=_SOCKET_TIMEOUT)


class ImapMailSource:
    def __init__(
        self,
        host: str,
        port: int,
        ssl: bool,
        user: str,
        password: str,
        folder: str,
    ) -> None:
        self._host = host
        self._port = port
        self._ssl = ssl
        self._user = user
        self._password = password
        self._folder = folder

    def _connect(self) -> MailBox | MailBoxUnencrypted:
        mb = _make_mailbox(self._host, self._port, self._ssl)
        mb.login(self._user, self._password, initial_folder=self._folder)
        return mb

    def fetch(self) -> list[Message]:
        messages: list[Message] = []
        with self._connect() as mb:
            for raw in mb.fetch(AND(seen=False), mark_seen=False, bulk=True):
                msg = self._parse(raw)
                if msg is not None:
                    messages.append(msg)
        return messages

    def delete(self, message_id: str) -> None:
        with self._connect() as mb:
            for raw in mb.fetch(AND(header=["Message-ID", message_id]), mark_seen=False):
                mb.delete([raw.uid])
                logger.info("Deleted message %s from mailbox", message_id)
                return
        logger.warning("Message %s not found for deletion", message_id)

    @staticmethod
    def _parse(raw: MailMessage) -> Message | None:
        message_id = (raw.headers.get("message-id") or [""])[0].strip()
        if not message_id:
            logger.warning("Skipping message with no Message-ID: subject=%r", raw.subject)
            return None

        attachments = [
            Attachment(
                filename=att.filename or "attachment",
                data=att.payload,
                content_type=att.content_type,
            )
            for att in raw.attachments
        ]

        return Message(
            message_id=message_id,
            sender=raw.from_ or "",
            subject=raw.subject or "",
            body_text=raw.text or "",
            attachments=attachments,
        )
