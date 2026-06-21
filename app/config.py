from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # IMAP
    imap_host: str
    imap_port: int = 993
    imap_ssl: bool = True
    imap_user: str
    imap_password: str
    imap_folder: str = "INBOX"
    poll_interval: int = 60

    # Security
    allowed_senders: str = ""
    allowed_senders_file: str = ""
    max_attachment_mb: int = 20
    allowed_extensions: str = "pdf,png,jpg,jpeg,docx,doc,xlsx,xls,odt,ods,txt"

    # Attachment handling
    print_attachments: Literal["FIRST", "ALL"] = "FIRST"
    printed_dir: Path = Path("/data/printed")

    # Post-print
    delete_from_mailbox: bool = True

    # Printer
    printer_name: str
    printer_uri: str
    print_default_orientation: Literal["P", "L"] = "P"
    print_default_sides: Literal[1, 2] = 2
    print_default_edge: Literal["s", "l"] = "l"

    # Misc
    db_path: Path = Path("/data/state.db")
    log_level: str = "INFO"

    @field_validator("print_default_sides", mode="before")
    @classmethod
    def coerce_sides(cls, v: object) -> int:
        return int(v)

    @model_validator(mode="after")
    def validate_printed_dir(self) -> "Settings":
        self.printed_dir.mkdir(parents=True, exist_ok=True)
        return self

    @property
    def allowed_extensions_set(self) -> set[str]:
        return {ext.strip().lower() for ext in self.allowed_extensions.split(",") if ext.strip()}

    @property
    def max_attachment_bytes(self) -> int:
        return self.max_attachment_mb * 1024 * 1024
