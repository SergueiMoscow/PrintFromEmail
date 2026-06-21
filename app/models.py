from dataclasses import dataclass, field
from enum import Enum


class Orientation(str, Enum):
    PORTRAIT = "P"
    LANDSCAPE = "L"


class Sides(str, Enum):
    ONE_SIDED = "one-sided"
    TWO_SIDED_LONG_EDGE = "two-sided-long-edge"
    TWO_SIDED_SHORT_EDGE = "two-sided-short-edge"


class PrintStatus(str, Enum):
    PRINTED = "printed"
    PARTIAL = "partial"
    REJECTED = "rejected"
    ERROR = "error"


@dataclass
class PrintOptions:
    orientation: Orientation
    sides: Sides


@dataclass
class Attachment:
    filename: str
    data: bytes
    content_type: str


@dataclass
class Message:
    message_id: str
    sender: str
    subject: str
    body_text: str
    attachments: list[Attachment] = field(default_factory=list)


@dataclass
class PrintResult:
    message_id: str
    sender: str
    subject: str
    status: PrintStatus
    saved_files: list[str] = field(default_factory=list)
    error: str | None = None
