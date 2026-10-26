import csv
import io
from pathlib import Path

from examc_app.models import Exam, PrepStudent

# The students list of the AMC project (options.xml "listeetudiants": %PROJET/students.csv), one copy per row.
STUDENTS_CSV_NAME = "students.csv"

# Column -> value of a student. exam_template.tex reads the file with csvsimple "head to column names": the columns
# become LaTeX macros (\ID, \SCIPER...), so their names must be letters only. AMC uses ID for the association and
# ID, SCIPER, NAME, SECTION, EMAIL in its exports; the review reads ID, SCIPER and NAME.
STUDENTS_CSV_COLUMNS = {
    "ID": lambda student: student.copy_no,
    "SCIPER": lambda student: student.sciper,
    # Like the csvgen lists: "First Last"
    "NAME": lambda student: f"{student.first_name} {student.last_name}".strip(),
    "LASTNAME": lambda student: student.last_name,
    "FIRSTNAME": lambda student: student.first_name,
    "EMAIL": lambda student: student.email or "",
    "SECTION": lambda student: student.section or "",
    "ROOM": lambda student: student.room or "",
    "SEAT": lambda student: student.seat,
}

# csvsimple does not read quoted values: a row with one of these characters would be skipped, without its copy
FORBIDDEN_CHARACTERS = (",", '"', "\n", "\r")


class StudentsCsvError(Exception):
    """The students list cannot be written: `errors` lists the problems, for the user."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def _student_label(student: PrepStudent) -> str:
    return f"ID {student.copy_no} (SCIPER {student.sciper})"


def students_csv_problems(exam: Exam) -> list[str]:
    """The problems preventing the students list of the exam from being written, for the user (empty when none)."""
    students = list(PrepStudent.objects.filter(exam=exam).order_by("copy_no", "pk"))
    if not students:
        return ["The exam has no students: import them in the Students page first."]

    problems = []
    to_correct = sum(student.needs_correction for student in students)
    if to_correct:
        problems.append(f"{to_correct} student(s) of the Students page must be corrected first "
                        "(SCIPER not found in the EPFL directory).")
    without_seat = sum(not student.seat for student in students)
    if without_seat:
        problems.append(f"{without_seat} student(s) of the Students page have no seat: give them one first.")

    copy_numbers = [student.copy_no for student in students]
    if copy_numbers != list(range(1, len(students) + 1)):
        problems.append("The IDs of the students must be 1, 2, 3... without gaps: renumber them in the Students page.")

    for student in students:
        bad_columns = [column for column, value in STUDENTS_CSV_COLUMNS.items()
                       if any(character in str(value(student)) for character in FORBIDDEN_CHARACTERS)]
        if bad_columns:
            problems.append(f"Student {_student_label(student)}: no comma or double quote allowed in "
                            f"{', '.join(column.lower() for column in bad_columns)}.")
    return problems


def build_students_csv(exam: Exam) -> str:
    """The students list of the exam for AMC (STUDENTS_CSV_COLUMNS), in the order of the IDs."""
    problems = students_csv_problems(exam)
    if problems:
        raise StudentsCsvError(problems)

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(STUDENTS_CSV_COLUMNS)
    for student in PrepStudent.objects.filter(exam=exam).order_by("copy_no", "pk"):
        writer.writerow([value(student) for value in STUDENTS_CSV_COLUMNS.values()])
    return buffer.getvalue()


def write_students_csv(exam: Exam, project_path) -> Path:
    """Writes (replaces) the students.csv of the AMC project of the exam. Raises StudentsCsvError."""
    path = Path(project_path) / STUDENTS_CSV_NAME
    path.write_text(build_students_csv(exam), encoding="utf-8")
    return path
