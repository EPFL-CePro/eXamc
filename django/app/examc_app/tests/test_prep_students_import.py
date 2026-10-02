import io

from django.test import SimpleTestCase, TestCase
from openpyxl import Workbook, load_workbook

from examc_app.models import PrepStudent
from examc_app.services.student.prep_import import (
    StudentsFileError, build_students_template, read_students_file, replace_prep_students,
)
from examc_app.tests.helpers.models import create_mock_exam

HEADER = ["ID", "SCIPER", "LAST NAME", "FIRST NAME", "EMAIL", "SECTION", "ROOM", "SEAT"]


def make_xlsx(rows: list[list]) -> bytes:
    workbook = Workbook()
    for row in rows:
        workbook.active.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


class ReadStudentsFileTestCase(SimpleTestCase):
    def test_xlsx_numbers_are_read_as_integers_text(self):
        content = make_xlsx([
            HEADER,
            [1, 123456, "Lovelace", "Ada", "ada@epfl.ch", "IN", "CO 1", "A1"],
            [2, 234567.0, "Turing", "Alan", None, None, None, 12],
            [None, None, None, None, None, None, None, None],
        ])

        students = read_students_file("students.xlsx", content)

        self.assertEqual(len(students), 2)
        self.assertEqual(students[0]["sciper"], "123456")
        self.assertEqual(students[1]["sciper"], "234567")
        self.assertEqual(students[1]["seat"], "12")
        self.assertEqual(students[1]["email"], "")

    def test_headers_ignore_case_spaces_and_order(self):
        content = make_xlsx([
            ["seat", "Last_Name", "first name", "Sciper", "id"],
            ["A1", "Lovelace", "Ada", 123456, 1],
        ])

        students = read_students_file("students.xlsx", content)

        self.assertEqual(students[0]["last_name"], "Lovelace")
        self.assertEqual(students[0]["copy_no"], "1")

    def test_all_row_errors_are_reported(self):
        content = make_xlsx([
            HEADER,
            [1, 123456, "Lovelace", "Ada", "not-an-email", None, None, "A1"],
            [1, 12345, "Turing", None, None, None, None, "A2"],
            [3, 123456, "Hopper", "Grace", None, None, None, "A3"],
        ])

        with self.assertRaises(StudentsFileError) as context:
            read_students_file("students.xlsx", content)

        errors = context.exception.errors
        self.assertEqual(len(errors), 3)
        self.assertIn("Row 2", errors[0])
        self.assertIn("email", errors[0])
        self.assertIn("ID 1 already used in row 2", errors[1])
        self.assertIn("SCIPER '12345' must have 6 digits", errors[1])
        self.assertIn("first name is empty", errors[1])
        self.assertIn("SCIPER 123456 already used in row 2", errors[2])

    def test_missing_required_columns(self):
        content = make_xlsx([["ID", "SCIPER", "NAME"], [1, 123456, "Ada Lovelace"]])

        with self.assertRaises(StudentsFileError) as context:
            read_students_file("students.xlsx", content)

        self.assertIn("LAST NAME, FIRST NAME, SEAT", context.exception.errors[0])

    def test_too_long_value(self):
        content = make_xlsx([HEADER, [1, 123456, "Lovelace", "Ada", None, "X" * 21, None, "A1"]])

        with self.assertRaises(StudentsFileError) as context:
            read_students_file("students.xlsx", content)

        self.assertIn("section is longer than 20 characters", context.exception.errors[0])

    def test_unsupported_or_broken_files(self):
        for name, content in [("students.csv", b"ID,SCIPER"), ("students.xls", b"x"), ("students.xlsx", b"not a zip")]:
            with self.subTest(name=name), self.assertRaises(StudentsFileError):
                read_students_file(name, content)

    def test_template_headers_are_accepted(self):
        template = load_workbook(io.BytesIO(build_students_template()))
        self.assertEqual(template.sheetnames, ["Students", "Help"])
        headers = [cell.value for cell in template["Students"][1]]
        self.assertEqual(headers, HEADER)

        # Empty template: only the header row
        with self.assertRaises(StudentsFileError) as context:
            read_students_file("students_template.xlsx", build_students_template())
        self.assertIn("no students", context.exception.errors[0])

        # Filled template
        template["Students"].append([1, 123456, "Lovelace", "Ada", None, None, None, "A1"])
        buffer = io.BytesIO()
        template.save(buffer)
        self.assertEqual(len(read_students_file("students_template.xlsx", buffer.getvalue())), 1)


class ReplacePrepStudentsTestCase(TestCase):
    def test_replaces_the_exam_students_only(self):
        exam = create_mock_exam()
        other_exam = create_mock_exam(code="OTHER")
        PrepStudent.objects.create(exam=exam, copy_no=9, sciper=999999, first_name="Old", last_name="Student", seat="Z")
        PrepStudent.objects.create(exam=other_exam, copy_no=1, sciper=111111, first_name="Keep", last_name="Me", seat="B")
        students = read_students_file("students.xlsx", make_xlsx([
            HEADER,
            [1, 123456, "Lovelace", "Ada", "ada@epfl.ch", "IN", "CO 1", "A1"],
            [2, 234567, "Turing", "Alan", None, None, None, "A2"],
        ]))

        result = replace_prep_students(exam, students)

        self.assertEqual((result.imported, result.replaced), (2, 1))
        self.assertEqual(
            list(exam.prepStudents.order_by("copy_no").values_list("copy_no", "sciper", "email", "room")),
            [(1, 123456, "ada@epfl.ch", "CO 1"), (2, 234567, None, None)],
        )
        self.assertEqual(other_exam.prepStudents.count(), 1)
        self.assertEqual(PrepStudent.history.filter(exam_id=exam.pk, history_type="+").count(), 3)
