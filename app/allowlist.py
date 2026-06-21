import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_allowlist(allowed_senders_env: str, allowed_senders_file: str) -> set[str]:
    """Load and merge sender allowlist from env variable and optional file."""
    senders: set[str] = set()

    for addr in allowed_senders_env.split(","):
        addr = addr.strip().lower()
        if addr:
            senders.add(addr)

    if allowed_senders_file:
        path = Path(allowed_senders_file)
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                addr = line.strip().lower()
                if addr and not addr.startswith("#"):
                    senders.add(addr)
        else:
            logger.warning("Allowed senders file not found: %s", allowed_senders_file)

    return senders


def is_allowed(sender: str, allowlist: set[str]) -> bool:
    """Check whether sender address is in the allowlist."""
    return sender.strip().lower() in allowlist
