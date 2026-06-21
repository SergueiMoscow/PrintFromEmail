import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_OFFICE_EXTENSIONS = {"docx", "doc", "xlsx", "xls", "odt", "ods"}
_PASSTHROUGH_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt"}


class NullConverter:
    """Returns the file unchanged (PDF and images need no conversion)."""

    def to_pdf(self, path: Path) -> Path:
        return path


class LibreOfficeConverter:
    """Converts office documents to PDF using LibreOffice headless."""

    def to_pdf(self, path: Path) -> Path:
        outdir = Path(tempfile.mkdtemp())
        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(outdir),
            str(path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            shutil.rmtree(outdir, ignore_errors=True)
            raise RuntimeError(
                f"LibreOffice conversion failed (rc={result.returncode}): {result.stderr}"
            )
        pdf_path = outdir / (path.stem + ".pdf")
        if not pdf_path.exists():
            shutil.rmtree(outdir, ignore_errors=True)
            raise RuntimeError(f"Expected PDF not found after conversion: {pdf_path}")
        return pdf_path


def get_converter(extension: str) -> NullConverter | LibreOfficeConverter:
    """Return the appropriate converter for the given file extension."""
    ext = extension.lower().lstrip(".")
    if ext in _OFFICE_EXTENSIONS:
        return LibreOfficeConverter()
    return NullConverter()
