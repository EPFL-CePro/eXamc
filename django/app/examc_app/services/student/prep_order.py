import random
import re
import unicodedata

from django.db import transaction
from simple_history.utils import bulk_update_with_history

from examc_app.models import Exam, PrepStudent


class StudentsOrderError(Exception):
    """The students cannot be reordered: `errors` lists the problems, for the user."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _text_key(text) -> str:
    """Ignoring case and accents (É sorted with E)."""
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().casefold()


def _natural_key(text) -> tuple:
    """'R1-2' before 'R1-10': the numbers are compared as numbers."""
    return tuple((0, int(part), "") if part.isdigit() else (1, 0, part)
                 for part in re.split(r"(\d+)", _text_key(text)) if part)


def _name_key(student: PrepStudent) -> tuple:
    # Students without names (SCIPER to correct) come last
    return not student.last_name, _text_key(student.last_name), _text_key(student.first_name)


# Order -> sort key of the students. "random" shuffles them.
ORDERS = {
    "name": _name_key,
    "sciper": lambda student: student.sciper,
    "section": lambda student: (not student.section, _text_key(student.section), *_name_key(student)),
    "seat": lambda student: (not student.room, _natural_key(student.room), not student.seat,
                             _natural_key(student.seat), *_name_key(student)),
}
ORDER_NAMES = (*ORDERS, "random")


def _renumber(students: list[PrepStudent]) -> None:
    """Copy numbers 1, 2, 3... in the order of `students`, saved with their history."""
    changed = []
    for copy_no, student in enumerate(students, start=1):
        if student.copy_no != copy_no:
            student.copy_no = copy_no
            changed.append(student)
    bulk_update_with_history(changed, PrepStudent, ["copy_no"])


def _exam_students(exam_id: int) -> list[PrepStudent]:
    return list(PrepStudent.objects.select_for_update().filter(exam_id=exam_id).order_by("copy_no", "pk"))


def reorder_prep_students(exam: Exam, order: str) -> int:
    """
    Gives the exam students the copy numbers (IDs) 1, 2, 3... in the `order` (ORDER_NAMES); the rooms and seats
    stay with each student. Returns the number of students.
    """
    if order not in ORDER_NAMES:
        raise StudentsOrderError([f"Unknown order '{order}'."])

    with transaction.atomic():
        students = _exam_students(exam.pk)
        if order == "random":
            random.SystemRandom().shuffle(students)
        else:
            students.sort(key=ORDERS[order])
        _renumber(students)
    return len(students)


def move_prep_student(student: PrepStudent, copy_no: int) -> None:
    """
    Gives `student` the copy number `copy_no` (1 to the number of students): the students in between shift by one,
    and the exam students are numbered 1, 2, 3... again.
    """
    with transaction.atomic():
        students = [s for s in _exam_students(student.exam_id) if s.pk != student.pk]
        if not 1 <= copy_no <= len(students) + 1:
            raise StudentsOrderError([f"The ID must be from 1 to {len(students) + 1}."])
        students.insert(copy_no - 1, student)
        _renumber(students)
