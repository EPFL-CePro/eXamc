import re
from dataclasses import dataclass

from django.db import transaction
from simple_history.utils import bulk_update_with_history

from examc_app.models import Exam, PrepStudent

# The run of "#" in a seat pattern is replaced by the seat number, with leading zeros up to its length:
# "R1-##" -> R1-01, R1-02... R1-99, R1-100
NUMBER_PLACEHOLDER_RE = re.compile(r"#+")


class SeatsAssignmentError(Exception):
    """The assignment cannot be done: `errors` lists the problems, for the user."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class SeatsAssignmentResult:
    updated: int
    first_seat: str | None = None
    last_seat: str | None = None


def format_seat(pattern: str, number: int) -> str:
    """'R1-##', 5 -> 'R1-05' (the pattern has one run of '#', see check_seat_pattern)."""
    return NUMBER_PLACEHOLDER_RE.sub(lambda match: str(number).zfill(len(match.group())), pattern, count=1)


def check_seat_pattern(pattern: str) -> str | None:
    """The problem of a seat pattern, for the user, or None."""
    runs = len(NUMBER_PLACEHOLDER_RE.findall(pattern))
    if runs == 0:
        return f"The seat pattern '{pattern}' has no '#' for the seat number (e.g. R1-##)."
    if runs > 1:
        return f"The seat pattern '{pattern}' must have only one group of '#' (e.g. R1-##)."
    return None


def assign_rooms_and_seats(exam: Exam, first_id: int, last_id: int, room: str = "", seat_pattern: str = "",
                           first_number: int = 1) -> SeatsAssignmentResult:
    """
    Gives to the students with an ID (copy number) from `first_id` to `last_id`, in the order of the IDs, the room
    `room` and the seats of `seat_pattern` numbered from `first_number` (see format_seat). An empty room or pattern
    keeps the current rooms or seats. All or nothing; raises SeatsAssignmentError with all the problems found.
    """
    room = (room or "").strip()
    seat_pattern = (seat_pattern or "").strip()

    errors = []
    if first_id < 1 or last_id < first_id:
        errors.append("The IDs must go from a first ID to a last ID that is not smaller, starting at 1.")
    if first_number < 0:
        errors.append("The first seat number cannot be negative.")
    if not room and not seat_pattern:
        errors.append("Give a room, a seat pattern, or both.")
    if seat_pattern and (problem := check_seat_pattern(seat_pattern)):
        errors.append(problem)
    for field, value in (("room", room), ("seat", seat_pattern)):
        max_length = PrepStudent._meta.get_field(field).max_length
        if len(value) > max_length:
            errors.append(f"The {field} is longer than {max_length} characters.")
    if errors:
        raise SeatsAssignmentError(errors)

    with transaction.atomic():
        students = list(PrepStudent.objects.select_for_update()
                        .filter(exam=exam, copy_no__gte=first_id, copy_no__lte=last_id)
                        .order_by("copy_no", "pk"))
        if not students:
            raise SeatsAssignmentError([f"No student has an ID from {first_id} to {last_id}."])

        fields = []
        if room:
            fields.append("room")
            for student in students:
                student.room = room
        if seat_pattern:
            fields.append("seat")
            for number, student in enumerate(students, start=first_number):
                student.seat = format_seat(seat_pattern, number)
                if len(student.seat) > PrepStudent._meta.get_field("seat").max_length:
                    raise SeatsAssignmentError([f"The seat {student.seat} is too long."])

        bulk_update_with_history(students, PrepStudent, fields)

    return SeatsAssignmentResult(updated=len(students), first_seat=students[0].seat if seat_pattern else None,
                                 last_seat=students[-1].seat if seat_pattern else None)
