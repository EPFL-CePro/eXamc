import io
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from openpyxl import Workbook, load_workbook
from openpyxl.comments import Comment
from openpyxl.styles import Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from simple_history.utils import bulk_create_with_history

from examc_app.models import Exam, PrepStudent


# Column header shown to the users (template file order) -> PrepStudent field
HEADER_FIELDS = {
    "ID": "copy_no",
    "SCIPER": "sciper",
    "LAST NAME": "last_name",
    "FIRST NAME": "first_name",
    "EMAIL": "email",
    "SECTION": "section",
    "ROOM": "room",
    "SEAT": "seat",
}
REQUIRED_FIELDS = ("copy_no", "sciper", "last_name", "first_name", "seat")
# Header -> (content, example), shown in the template file
HEADER_HELP = {
    "ID": ("Copy number: whole number, unique in the exam", 1),
    "SCIPER": ("SCIPER: 6 digits, unique in the exam", 123456),
    "LAST NAME": ("Last name", "Lovelace"),
    "FIRST NAME": ("First name", "Ada"),
    "EMAIL": ("Email address", "ada.lovelace@epfl.ch"),
    "SECTION": ("Section, up to 20 characters", "IN"),
    "ROOM": ("Room", "CO 1"),
    "SEAT": ("Seat", "A12"),
}
TEXT_FIELDS = ("last_name", "first_name", "email", "section", "room", "seat")

SCIPER_RE = re.compile(r"^\d{6}$")


class StudentsFileError(Exception):
    """The file cannot be imported: `errors` lists the problems, for the user."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class StudentsImportResult:
    imported: int
    replaced: int


def _normalize_header(value) -> str:
    """'Last name', 'LAST_NAME', ' lastname ' -> 'lastname'"""
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", text.lower())


def _cell_text(value) -> str:
    """Spreadsheet cell -> text: Excel stores 123456 as 123456.0"""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _read_xlsx_rows(content: bytes) -> list[list]:
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise StudentsFileError(["The file is not a valid Excel (.xlsx) file."])

    try:
        return [list(row) for row in workbook.worksheets[0].iter_rows(values_only=True)]
    finally:
        workbook.close()


def read_students_file(file_name: str, content: bytes) -> list[dict]:
    """
    Reads the students of the first sheet of an .xlsx file, whose first row holds the column headers
    (HEADER_FIELDS, case, spaces and underscores ignored). Raises StudentsFileError with all the problems found.
    """
    if Path(file_name).suffix.lower() != ".xlsx":
        raise StudentsFileError([f"'{file_name}' is not an Excel (.xlsx) file: "
                                 "download the template, fill it and import it."])

    rows = _read_xlsx_rows(content)
    # Rows left empty (often at the end of a spreadsheet) are ignored
    rows = [(number, row) for number, row in enumerate(rows, start=1) if any(_cell_text(v) for v in row)]
    if not rows:
        raise StudentsFileError(["The file is empty."])

    header_number, header = rows[0]
    fields_by_header = {_normalize_header(h): field for h, field in HEADER_FIELDS.items()}
    field_by_index = {}
    for index, value in enumerate(header):
        field = fields_by_header.get(_normalize_header(value))
        if field and field not in field_by_index.values():
            field_by_index[index] = field

    missing = [h for h, field in HEADER_FIELDS.items()
               if field in REQUIRED_FIELDS and field not in field_by_index.values()]
    if missing:
        raise StudentsFileError([f"Missing column(s) in row {header_number}: {', '.join(missing)}. "
                                 f"Expected columns: {', '.join(HEADER_FIELDS)}."])

    max_lengths = {field: PrepStudent._meta.get_field(field).max_length for field in TEXT_FIELDS}

    errors = []
    students = []
    seen_copy_no = {}
    seen_sciper = {}

    for number, row in rows[1:]:
        student = {field: _cell_text(row[index]) if index < len(row) else "" for index, field in field_by_index.items()}
        row_errors = [f"{field.replace('_', ' ')} is empty" for field in REQUIRED_FIELDS if not student.get(field)]

        if student.get("copy_no"):
            if not student["copy_no"].isdigit() or int(student["copy_no"]) < 1:
                row_errors.append(f"ID '{student['copy_no']}' must be a positive whole number")
            elif student["copy_no"] in seen_copy_no:
                row_errors.append(f"ID {student['copy_no']} already used in row {seen_copy_no[student['copy_no']]}")
            else:
                seen_copy_no[student["copy_no"]] = number

        if student.get("sciper"):
            if not SCIPER_RE.match(student["sciper"]):
                row_errors.append(f"SCIPER '{student['sciper']}' must have 6 digits")
            elif student["sciper"] in seen_sciper:
                row_errors.append(f"SCIPER {student['sciper']} already used in row {seen_sciper[student['sciper']]}")
            else:
                seen_sciper[student["sciper"]] = number

        for field, max_length in max_lengths.items():
            if len(student.get(field, "")) > max_length:
                row_errors.append(f"{field.replace('_', ' ')} is longer than {max_length} characters")

        if student.get("email"):
            try:
                validate_email(student["email"])
            except ValidationError:
                row_errors.append(f"email '{student['email']}' is not valid")

        if row_errors:
            errors.append(f"Row {number}: {', '.join(row_errors)}.")
        else:
            students.append(student)

    if errors:
        raise StudentsFileError(errors)
    if not students:
        raise StudentsFileError(["The file has a header row but no students."])
    return students


def replace_prep_students(exam: Exam, students: list[dict]) -> StudentsImportResult:
    """Replaces all the prep students of the exam by `students` (from read_students_file), all or nothing."""
    with transaction.atomic():
        current = PrepStudent.objects.filter(exam=exam)
        replaced = current.count()
        current.delete()
        bulk_create_with_history([
            PrepStudent(
                exam=exam,
                copy_no=int(student["copy_no"]),
                sciper=int(student["sciper"]),
                last_name=student["last_name"],
                first_name=student["first_name"],
                email=student.get("email") or None,
                section=student.get("section") or None,
                room=student.get("room") or None,
                seat=student["seat"],
            )
            for student in students
        ], PrepStudent)
    return StudentsImportResult(imported=len(students), replaced=replaced)


def build_students_template() -> bytes:
    """
    Excel file to fill for read_students_file: a "Students" sheet with the headers (required ones highlighted,
    a comment on each) and a "Help" sheet describing the columns.
    """
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Students"

    required_fill = PatternFill("solid", fgColor="1F4E79")
    optional_fill = PatternFill("solid", fgColor="D9E1F2")
    for column, (header, field) in enumerate(HEADER_FIELDS.items(), start=1):
        required = field in REQUIRED_FIELDS
        content, _ = HEADER_HELP[header]
        cell = sheet.cell(row=1, column=column, value=header)
        cell.font = Font(bold=True, color="FFFFFF" if required else "1F2937")
        cell.fill = required_fill if required else optional_fill
        cell.comment = Comment(f"{'Required' if required else 'Optional'}. {content}.", "eXamc")
        sheet.column_dimensions[cell.column_letter].width = 26 if field == "email" else 16
    sheet.freeze_panes = "A2"

    # Excel warns on a wrong ID or SCIPER while typing
    id_validation = DataValidation(type="whole", operator="greaterThanOrEqual", formula1="1", showErrorMessage=True,
                                   errorTitle="ID", error="The ID must be a whole number, 1 or more.")
    sciper_validation = DataValidation(type="whole", operator="between", formula1="100000", formula2="999999",
                                       showErrorMessage=True, errorTitle="SCIPER", error="The SCIPER must have 6 digits.")
    sheet.add_data_validation(id_validation)
    sheet.add_data_validation(sciper_validation)
    id_validation.add("A2:A5000")
    sciper_validation.add("B2:B5000")

    help_sheet = workbook.create_sheet("Help")
    help_sheet.append(["Only the first sheet (Students) is imported. Keep its first row unchanged, "
                       "one student per row. Importing replaces all the students of the exam."])
    help_sheet.append([])
    help_sheet.append(["Column", "Required", "Content", "Example"])
    for cell in help_sheet[3]:
        cell.font = Font(bold=True)
    for header, field in HEADER_FIELDS.items():
        content, example = HEADER_HELP[header]
        help_sheet.append([header, "Required" if field in REQUIRED_FIELDS else "Optional", content, example])
    for letter, width in zip("ABCD", (14, 12, 48, 24)):
        help_sheet.column_dimensions[letter].width = width

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
