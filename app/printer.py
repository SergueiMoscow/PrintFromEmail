import logging
import subprocess
from pathlib import Path

from app.models import Orientation, PrintOptions

logger = logging.getLogger(__name__)

_ORIENTATION_MAP = {
    Orientation.PORTRAIT: "3",
    Orientation.LANDSCAPE: "4",
}


def build_lp_args(printer_name: str, options: PrintOptions, pdf_path: Path) -> list[str]:
    """Build the lp command argument list."""
    return [
        "lp",
        "-d", printer_name,
        "-o", f"orientation-requested={_ORIENTATION_MAP[options.orientation]}",
        "-o", f"sides={options.sides.value}",
        str(pdf_path),
    ]


class CupsPrinter:
    def __init__(self, printer_name: str) -> None:
        self._printer_name = printer_name

    def print(self, pdf_path: Path, options: PrintOptions) -> None:
        """Send PDF to CUPS printer. Raises RuntimeError on failure."""
        args = build_lp_args(self._printer_name, options, pdf_path)
        logger.debug("Running: %s", " ".join(args))
        result = subprocess.run(args, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                f"lp failed (rc={result.returncode}): {result.stderr.strip()}"
            )
        logger.info("Sent to printer %s: %s", self._printer_name, pdf_path.name)
