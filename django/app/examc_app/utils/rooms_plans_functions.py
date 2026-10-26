import csv
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

ROOMS_PLANS_ROOT = Path(settings.ROOMS_PLANS_ROOT)
MAP_DIR = ROOMS_PLANS_ROOT / "map"
CSV_DIR = ROOMS_PLANS_ROOT / "csv"
EXPORT_DIR = ROOMS_PLANS_ROOT / "export"
SPECIAL_DIR = ROOMS_PLANS_ROOT / "csv_special_numbers"
FONT_PATH = ROOMS_PLANS_ROOT / "NotoSans-Bold.ttf"

FONT_SIZE = 10
CIRCLE_RADIUS = 11
SQUARE_HALF_SIDE = 9
TEXT_COLOR = "red"

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


class RoomPlanError(Exception):
    """A plan can't be generated; the message is meant for the user."""


@dataclass(frozen=True)
class RoomPlan:
    """One room to draw: plan image, seat coordinates, output file and seat range."""

    image_file: str   # in map/
    csv_file: str     # in csv/, one "x,y" row per seat
    export_file: str  # written to export/
    first_seat: int
    last_seat: int


# ---------------------------------------------------------------------------
# CSV reading
# ---------------------------------------------------------------------------

def _read_rows(path: Path) -> list[list[str]]:
    """Non-empty CSV rows, with every cell stripped."""
    with path.open(newline="") as file:
        rows = ([cell.strip() for cell in row] for row in csv.reader(file))
        return [row for row in rows if any(row)]


def read_seat_coordinates(path: Path) -> list[tuple[int, int]]:
    coordinates: list[tuple[int, int]] = []
    for row_no, row in enumerate(_read_rows(path), start=1):
        try:
            coordinates.append((round(float(row[0])), round(float(row[1]))))
        except (IndexError, ValueError) as error:
            raise RoomPlanError(f"{path.name}, row {row_no}: expected \"x,y\", got \"{','.join(row)}\"") from error
    return coordinates


def read_first_column(path: Path) -> list[str]:
    return [row[0] for row in _read_rows(path)]


def read_skip_numbers(path: Path) -> set[int]:
    numbers: set[int] = set()
    for row_no, value in enumerate(read_first_column(path), start=1):
        try:
            numbers.add(int(value))
        except ValueError as error:
            raise RoomPlanError(f"{path.name}, row {row_no}: \"{value}\" is not a seat number to skip") from error
    return numbers


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _draw_seat(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, shape: str, font: Font) -> None:
    if shape == "circle":
        r = CIRCLE_RADIUS
        draw.ellipse([(x - r, y - r), (x + r, y + r)], fill="white", outline="black")
    elif shape == "square":
        h = SQUARE_HALF_SIDE
        draw.rectangle([(x - h, y - h), (x + h, y + h)], fill="white", outline="black")

    draw.text((x + 1, y), text, fill=TEXT_COLOR, anchor="mm", font=font)


def _draw_room(
    room: RoomPlan,
    *,
    special_numbers: list[str] | None,
    skip_numbers: set[int],
    shape: str,
    font: Font,
) -> None:
    # RGB so red text stays red on grayscale plans, and PNG/palette plans can be saved as JPEG
    with Image.open(MAP_DIR / room.image_file) as source:
        image = source.convert("RGB")
    draw = ImageDraw.Draw(image)

    number = room.first_seat
    for index, (x, y) in enumerate(read_seat_coordinates(CSV_DIR / room.csv_file)):
        if special_numbers is not None:
            # Special numbering: the file's values in order, nothing once they run out
            text = special_numbers[index] if index < len(special_numbers) else ""
        else:
            while number in skip_numbers:
                number += 1
            text = str(number)

        _draw_seat(draw, x, y, text, shape, font)

        number += 1
        if number > room.last_seat:
            break

    image.save(EXPORT_DIR / room.export_file)


def generate_plans(
    rooms: Sequence[RoomPlan],
    *,
    numbering_option: str,
    skipping_option: str,
    special_file: str,
    shape: str,
) -> None:
    """
    Draw the seat numbers of every room and save each plan to export/.

    special_file is a file name in csv_special_numbers/, or "" for none. It holds the
    numbers to show (special numbering) or the numbers to skip (skip option).
    Raises RoomPlanError with a message for the user.
    """
    special_path = SPECIAL_DIR / special_file if special_file else None

    if numbering_option == "special" and special_path is None:
        raise RoomPlanError("Special numbering needs a special numbering CSV file.")

    try:
        font = ImageFont.truetype(str(FONT_PATH), FONT_SIZE)

        # Read the special file once for all rooms
        special_numbers = (
            read_first_column(special_path) if numbering_option == "special" and special_path else None
        )
        # Skipped numbers only apply to normal numbering
        skip_numbers = (
            read_skip_numbers(special_path)
            if skipping_option == "skip" and special_path and special_numbers is None
            else set()
        )

        for room in rooms:
            _draw_room(room, special_numbers=special_numbers, skip_numbers=skip_numbers, shape=shape, font=font)

    except FileNotFoundError as error:
        logger.exception("Room plan file missing")
        raise RoomPlanError(f"Missing file: {Path(str(error.filename)).name}") from error
    except OSError as error:
        logger.exception("Room plan generation failed")
        raise RoomPlanError(f"Could not read or write a plan file: {error}") from error