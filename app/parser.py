import logging

from app.models import Orientation, PrintOptions, Sides

logger = logging.getLogger(__name__)

_VALID_ORIENTATIONS = {"P", "L"}
_VALID_SIDES = {"1", "2"}
_VALID_EDGES = {"S", "L"}


def _build_sides(sides_char: str, edge_char: str) -> Sides:
    if sides_char == "1":
        return Sides.ONE_SIDED
    if edge_char == "S":
        return Sides.TWO_SIDED_SHORT_EDGE
    return Sides.TWO_SIDED_LONG_EDGE


def parse_print_options(body: str, defaults: PrintOptions) -> PrintOptions:
    """Extract print options from the first 3 non-whitespace characters of the email body.

    Returns defaults unchanged if the code is missing or invalid.
    """
    stripped = "".join(body.split())
    if len(stripped) < 3:
        return defaults

    code = stripped[:3].upper()
    orientation_char, sides_char, edge_char = code[0], code[1], code[2]

    if (
        orientation_char not in _VALID_ORIENTATIONS
        or sides_char not in _VALID_SIDES
        or edge_char not in _VALID_EDGES
    ):
        logger.debug("Invalid print code %r, using defaults", code)
        return defaults

    return PrintOptions(
        orientation=Orientation(orientation_char),
        sides=_build_sides(sides_char, edge_char),
    )
