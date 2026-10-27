import csv
import logging
import math
import secrets
import zipfile
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import UploadedFile
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.generic.edit import FormView

from examc_app.forms.misc import SeatingForm, SeatingSpecialForm
from examc_app.utils.rooms_plans_functions import (
    RoomPlan,
    RoomPlanError,
    generate_plans,
)
from examc_app.utils.view_context_helpers import ViewContext

logger = logging.getLogger(__name__)

ROOMS_PLANS_ROOT = Path(settings.ROOMS_PLANS_ROOT)
CSV_DIR = ROOMS_PLANS_ROOT / "csv"
MAP_DIR = ROOMS_PLANS_ROOT / "map"
EXPORT_DIR = ROOMS_PLANS_ROOT / "export"
SPECIAL_DIR = ROOMS_PLANS_ROOT / "csv_special_numbers"

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png")

SeatRange = tuple[int, int]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def csv_to_image_map(csv_dir: Path, image_dir: Path) -> dict[str, str]:
    """Map each room CSV file name to the plan image with the same name (case-insensitive)."""
    images = {
        path.stem.lower(): path.name
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    }
    return {
        path.name: images[path.stem.lower()]
        for path in csv_dir.glob("*.csv")
        if path.stem.lower() in images
    }


CSV_TO_JPG_MAP = csv_to_image_map(CSV_DIR, MAP_DIR)


def count_csv_lines(file_path: Path) -> int | None:
    """Number of non-empty rows in a CSV file, or None if it can't be read."""
    try:
        with file_path.open(newline="") as file:
            return sum(1 for row in csv.reader(file) if any(row))
    except (OSError, csv.Error, UnicodeDecodeError):
        logger.exception("Error reading CSV file %s", file_path)
        return None


def calculate_seat_numbers(
    seat_counts: list[int],
    first_seat_number: int,
    last_seat_number: int,
) -> tuple[list[int], list[int]]:
    """
    Split [first_seat_number, last_seat_number] across rooms in proportion to their size.
    Returns (first numbers, last numbers), one per room. Raises ValueError if impossible.
    """
    total_seats = sum(seat_counts)
    if total_seats == 0:
        raise ValueError("The selected rooms have no seats")

    ratio = min((last_seat_number - first_seat_number + 1) / total_seats, 1)

    firsts: list[int] = []
    lasts: list[int] = []
    next_first = first_seat_number

    for index, count in enumerate(seat_counts):
        last = math.ceil(count * ratio) + next_first - 1
        if index == len(seat_counts) - 1:
            last = min(last, last_seat_number)
        if last < next_first:
            raise ValueError("Negative number of seats selected")

        firsts.append(next_first)
        lasts.append(last)
        next_first = last + 1

    return firsts, lasts


def seat_ranges(
    seat_counts: list[int],
    *,
    numbering_option: str,
    skipping_option: str,
    fill_all_seats: bool,
    first_seat_number: int,
    last_seat_number: int | None,
    special_count: int | None,
) -> list[SeatRange]:
    """First and last seat number for each room. Raises ValueError if impossible."""
    special_numbering = skipping_option != "skip" and numbering_option == "special"

    if special_numbering:
        if special_count is None:
            raise ValueError("Special numbering needs a special numbering CSV file. Upload one and try again.")
        if not fill_all_seats and last_seat_number is None:
            raise ValueError('Enter a last seat number, or tick "Fill all seats" to use every number in the special file.')

    split_firsts: list[int] = []
    split_lasts: list[int] = []
    if not fill_all_seats and not special_numbering:
        split_firsts, split_lasts = calculate_seat_numbers(
            seat_counts, first_seat_number, last_seat_number or sum(seat_counts)
        )

    ranges: list[SeatRange] = []
    current = first_seat_number
    previous_last = 0

    for index, count in enumerate(seat_counts):
        first: int
        last: int

        if skipping_option == "skip" and fill_all_seats:
            # Same numbering as the original code, including the +1000 on the first room
            if index == 0:
                first = first_seat_number
                last = first + count + 1000 - 1
            else:
                first = previous_last + 1
                last = previous_last + count - 1
        elif special_numbering:
            # Checked above: special_count is set, and last_seat_number is set unless filling all seats
            assert special_count is not None
            first = 1
            if fill_all_seats or last_seat_number is None:
                last = first + special_count - 1
            else:
                last = last_seat_number
        elif fill_all_seats:
            first = current
            last = current + count - 1
        else:
            first, last = split_firsts[index], split_lasts[index]

        current = previous_last = last
        current += 1

        ranges.append((first, last))

    return ranges


def get_user_token(request: HttpRequest) -> str:
    token: str | None = request.session.get("user_token")
    if token is None:
        token = secrets.token_hex(16)
        request.session["user_token"] = token
    return token


def remove_files(directory: Path, pattern: str) -> None:
    for path in directory.glob(pattern):
        if path.is_file():
            path.unlink(missing_ok=True)


def export_file_name(image_file: str, token: str) -> str:
    return f"{Path(image_file).stem}_{token}_export.jpg"


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

class GenerateRoomPlanView(FormView):
    """
    One page with two tabs: "default" (this form, generated on the server) and
    "special" (labels placed in the browser). Open on the special tab with
    GenerateRoomPlanView.as_view(extra_context={"curr_tab": "special"}).
    """

    template_name = "public/rooms_plans.html"
    form_class = SeatingForm

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        base_context = super().get_context_data(**kwargs)
        view_context = ViewContext(
            base_dict=base_context,
            curr_tab="automatic"
        )

        # non generic context variables
        view_context.update(
            forms={
                "default": base_context["form"],
                "manual": SeatingSpecialForm(prefix="special")
            }
        )

        # The prefix keeps the special form's names and ids apart from the default form's
        return view_context.as_dict()

    def form_valid(self, form: SeatingForm) -> HttpResponse:
        data = form.cleaned_data
        csv_files: list[str] = data["csv_file"]
        numbering_option: str = data["numbering_option"]
        skipping_option: str = data["skipping_option"]
        fill_all_seats: bool = data["fill_all_seats"]
        shape_to_draw = data["shape_to_draw"]

        # Empty "first seat number" means start at 1
        first_seat_number: int = data["first_seat_number"] if data["first_seat_number"] is not None else 1

        token = get_user_token(self.request)

        # Room images
        missing = [csv_file for csv_file in csv_files if csv_file not in CSV_TO_JPG_MAP]
        if missing:
            return HttpResponse(f"No plan image found for: {', '.join(missing)}", status=404)
        image_files = [CSV_TO_JPG_MAP[csv_file] for csv_file in csv_files]

        # Seats per room (each CSV is read once)
        seat_counts: list[int] = []
        for csv_file in csv_files:
            count = count_csv_lines(CSV_DIR / csv_file)
            if count is None:
                return HttpResponse(f"Error reading CSV file: {csv_file}", status=500)
            seat_counts.append(count)

        # Special numbering file (new upload, or the one kept from a previous request)
        special_path = self._special_file_path(data["special_file"], token)
        special_count = count_csv_lines(Path(special_path)) if special_path else None

        # Special numbering reads its numbers from the file, whatever the skip option.
        # (Skipping without a file just skips nothing.)
        if numbering_option == "special" and special_path is None:
            return HttpResponse(
                "Special numbering needs a special numbering CSV file. Upload one and try again.", status=400
            )

        # generate_plans builds the path itself from csv_special_numbers/ + this name,
        # and treats an empty string as "no file"
        special_name = Path(special_path).name if special_path else ""

        try:
            ranges = seat_ranges(
                seat_counts,
                numbering_option=numbering_option,
                skipping_option=skipping_option,
                fill_all_seats=fill_all_seats,
                first_seat_number=first_seat_number,
                last_seat_number=data["last_seat_number"],
                special_count=special_count,
            )
        except ValueError as error:
            return HttpResponse(str(error), status=400)

        rooms = [
            RoomPlan(
                image_file=image_file,
                csv_file=csv_file,
                export_file=export_file_name(image_file, token),
                first_seat=first,
                last_seat=last,
            )
            for image_file, csv_file, (first, last) in zip(image_files, csv_files, ranges)
        ]

        # Only remove this user's previous exports, not everyone's
        remove_files(EXPORT_DIR, f"*_{token}_export.*")

        try:
            generate_plans(
                rooms,
                numbering_option=numbering_option,
                skipping_option=skipping_option,
                special_file=special_name,
                shape=shape_to_draw,
            )
        except RoomPlanError as error:
            return HttpResponse(f"Error during plan generation: {error}", status=500)

        export_paths = [EXPORT_DIR / room.export_file for room in rooms]

        if self.request.POST.get("action") == "download":
            zip_path = EXPORT_DIR / f"seat_map_{token}_export.zip"
            with zipfile.ZipFile(zip_path, "w") as archive:
                for export_path in export_paths:
                    archive.write(export_path, export_path.name)
            return FileResponse(zip_path.open("rb"), as_attachment=True, filename=zip_path.name)

        # "preview" (and the default)
        return render(
            self.request,
            self.template_name,
            self.get_context_data(
                form=form,
                curr_tab="default",
                export_files=[reverse("room_plan_file", args=["export", path.name]) for path in export_paths],
                special_file=special_path,
            ),
        )

    def _special_file_path(self, uploaded: UploadedFile | None, token: str) -> str | None:
        """Save a newly uploaded special file, or reuse the one stored in the session."""
        session = self.request.session

        if uploaded is None:
            stored: str | None = session.get("special_file_path")
            return stored if stored and Path(stored).is_file() else None

        # Replace only this user's previous file
        remove_files(SPECIAL_DIR, f"{token}_*")
        storage = FileSystemStorage(location=SPECIAL_DIR)
        saved_name = storage.save(f"{token}_{Path(uploaded.name or 'special.csv').name}", uploaded)
        path = storage.path(saved_name)
        session["special_file_path"] = path
        return path


# ---------------------------------------------------------------------------
# Room plan images (open to anonymous users, see LOGIN_REQUIRED_IGNORE_PATHS)
# ---------------------------------------------------------------------------


def get_room_plan_file(request: HttpRequest, folder: str, filename: str) -> FileResponse:
    """
    Serve a room plan image.

    map:    looked up by room name, with or without extension ("CO_1", "CO_1.csv" and
            "CO_1.jpg" all give the CO_1 plan), so both room selects can use it.
    export: only readable by the session that generated it.
    """
    if folder == "map":
        room = Path(filename).stem.lower()
        path = next(
            (
                image
                for image in MAP_DIR.iterdir()
                if image.is_file() and image.suffix.lower() in IMAGE_EXTENSIONS and image.stem.lower() == room
            ),
            None,
        )
        if path is None:
            raise Http404
        return FileResponse(path.open("rb"))

    if folder == "export":
        token = request.session.get("user_token")
        if not token:
            raise Http404

        # Only accept a bare filename: no separators, no "..", no absolute paths
        if Path(filename).name != filename or "\\" in filename:
            raise Http404

        export_dir = EXPORT_DIR.resolve()
        path = (export_dir / filename).resolve()
        if path.parent != export_dir or not path.is_file():
            raise Http404

        # Check the token against what will actually be served
        if f"_{token}_export" not in path.name:
            raise Http404

        return FileResponse(path.open("rb"))

    raise Http404