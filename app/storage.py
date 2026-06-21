import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.models import Attachment

logger = logging.getLogger(__name__)


class LocalAttachmentStorage:
    def __init__(self, storage_dir: Path) -> None:
        self._dir = storage_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, attachment: Attachment, message_id: str) -> str:
        """Save attachment to storage directory with a unique name. Returns filename."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        id_hash = hashlib.sha1(message_id.encode()).hexdigest()[:8]
        filename = f"{timestamp}_{id_hash}_{attachment.filename}"
        dest = self._dir / filename
        dest.write_bytes(attachment.data)
        logger.debug("Saved attachment: %s", filename)
        return filename
