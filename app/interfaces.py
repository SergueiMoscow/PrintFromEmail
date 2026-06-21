from pathlib import Path
from typing import Protocol

from app.models import Attachment, Message, PrintOptions, PrintResult


class MailSource(Protocol):
    def fetch(self) -> list[Message]:
        """Fetch unread messages with attachments."""
        ...

    def delete(self, message_id: str) -> None:
        """Delete message by Message-ID."""
        ...


class Printer(Protocol):
    def print(self, pdf_path: Path, options: PrintOptions) -> None:
        """Send PDF to printer with given options. Raises on failure."""
        ...


class Converter(Protocol):
    def to_pdf(self, path: Path) -> Path:
        """Convert file to PDF. Returns path to resulting PDF."""
        ...


class StateStore(Protocol):
    def is_processed(self, message_id: str) -> bool:
        """Return True if message was already processed."""
        ...

    def record(self, result: PrintResult) -> None:
        """Persist processing result."""
        ...


class AttachmentStorage(Protocol):
    def save(self, attachment: Attachment, message_id: str) -> str:
        """Save attachment bytes to storage. Returns filename."""
        ...
