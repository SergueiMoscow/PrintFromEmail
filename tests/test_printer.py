from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.models import Orientation, PrintOptions, Sides
from app.printer import CupsPrinter, build_lp_args


@pytest.mark.parametrize(
    "options, expected_orientation, expected_sides",
    [
        (
            PrintOptions(Orientation.PORTRAIT, Sides.ONE_SIDED),
            "3", "one-sided",
        ),
        (
            PrintOptions(Orientation.LANDSCAPE, Sides.TWO_SIDED_LONG_EDGE),
            "4", "two-sided-long-edge",
        ),
        (
            PrintOptions(Orientation.PORTRAIT, Sides.TWO_SIDED_SHORT_EDGE),
            "3", "two-sided-short-edge",
        ),
    ],
)
def test_build_lp_args(
    options: PrintOptions,
    expected_orientation: str,
    expected_sides: str,
) -> None:
    pdf_path = Path("/tmp/test.pdf")
    args = build_lp_args("office", options, pdf_path)

    assert args[0] == "lp"
    assert "-d" in args
    assert args[args.index("-d") + 1] == "office"
    assert f"orientation-requested={expected_orientation}" in " ".join(args)
    assert f"sides={expected_sides}" in " ".join(args)
    assert str(pdf_path) in args


def test_cups_printer_success() -> None:
    printer = CupsPrinter("office")
    options = PrintOptions(Orientation.PORTRAIT, Sides.ONE_SIDED)

    mock_result = MagicMock()
    mock_result.returncode = 0

    with patch("app.printer.subprocess.run", return_value=mock_result) as mock_run:
        printer.print(Path("/tmp/doc.pdf"), options)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "lp"


def test_cups_printer_failure_raises() -> None:
    printer = CupsPrinter("office")
    options = PrintOptions(Orientation.PORTRAIT, Sides.ONE_SIDED)

    mock_result = MagicMock()
    mock_result.returncode = 1
    mock_result.stderr = "Printer not found"

    with patch("app.printer.subprocess.run", return_value=mock_result):
        with pytest.raises(RuntimeError, match="lp failed"):
            printer.print(Path("/tmp/doc.pdf"), options)
