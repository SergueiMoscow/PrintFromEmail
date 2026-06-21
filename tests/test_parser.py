import pytest

from app.models import Orientation, PrintOptions, Sides
from app.parser import parse_print_options

DEFAULTS = PrintOptions(orientation=Orientation.PORTRAIT, sides=Sides.TWO_SIDED_LONG_EDGE)


@pytest.mark.parametrize(
    "body, expected",
    [
        # Valid codes
        ("P2l some text", PrintOptions(Orientation.PORTRAIT, Sides.TWO_SIDED_LONG_EDGE)),
        ("P2s some text", PrintOptions(Orientation.PORTRAIT, Sides.TWO_SIDED_SHORT_EDGE)),
        ("L2l some text", PrintOptions(Orientation.LANDSCAPE, Sides.TWO_SIDED_LONG_EDGE)),
        ("L1s some text", PrintOptions(Orientation.LANDSCAPE, Sides.ONE_SIDED)),
        ("P1s some text", PrintOptions(Orientation.PORTRAIT, Sides.ONE_SIDED)),
        # Lowercase normalised
        ("p2l some text", PrintOptions(Orientation.PORTRAIT, Sides.TWO_SIDED_LONG_EDGE)),
        ("l2s some text", PrintOptions(Orientation.LANDSCAPE, Sides.TWO_SIDED_SHORT_EDGE)),
        # Leading whitespace before code
        ("  \t P2l rest", PrintOptions(Orientation.PORTRAIT, Sides.TWO_SIDED_LONG_EDGE)),
        # Code surrounded by newlines
        ("\nL1l\nsome text", PrintOptions(Orientation.LANDSCAPE, Sides.ONE_SIDED)),
    ],
)
def test_valid_codes(body: str, expected: PrintOptions) -> None:
    assert parse_print_options(body, DEFAULTS) == expected


@pytest.mark.parametrize(
    "body",
    [
        "",                  # empty
        "P2",               # too short
        "X2l some text",    # invalid orientation
        "P3l some text",    # invalid sides
        "P2x some text",    # invalid edge
        "Hello world",      # no code at all
        "123 abc",          # wrong chars
    ],
)
def test_invalid_codes_return_defaults(body: str) -> None:
    assert parse_print_options(body, DEFAULTS) == DEFAULTS


def test_edge_ignored_for_one_sided() -> None:
    # When sides=1, edge char is present but sides should be ONE_SIDED regardless
    result = parse_print_options("P1l text", DEFAULTS)
    assert result.sides == Sides.ONE_SIDED
