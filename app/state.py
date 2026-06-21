import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.models import PrintResult

logger = logging.getLogger(__name__)

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS processed (
    message_id   TEXT PRIMARY KEY,
    sender       TEXT,
    subject      TEXT,
    status       TEXT,
    saved_files  TEXT,
    error        TEXT,
    processed_at TEXT
)
"""


class SqliteStateStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(_CREATE_TABLE)

    def is_processed(self, message_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed WHERE message_id = ?", (message_id,)
            ).fetchone()
        return row is not None

    def record(self, result: PrintResult) -> None:
        processed_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO processed
                    (message_id, sender, subject, status, saved_files, error, processed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.message_id,
                    result.sender,
                    result.subject,
                    result.status.value,
                    json.dumps(result.saved_files),
                    result.error,
                    processed_at,
                ),
            )
        logger.debug("Recorded result for %s: %s", result.message_id, result.status.value)
