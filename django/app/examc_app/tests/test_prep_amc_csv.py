import tempfile
from pathlib import Path

from django.test import TestCase

from examc_app.models import PrepStudent
from examc_app.services.student.prep_amc_csv import (
    StudentsCsvError, build_students_csv, students_csv_problems, write_students_csv,
)
from examc_app.tests.helpers.models import create_mock_exam
from examc_app.utils.amc.amc_build_functions import compute_exam_source_hash


class StudentsCsvTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()
        PrepStudent.objects.create(exam=self.exam, copy_no=2, sciper=234567, first_name="Alan", last_name="Turing",
                                   seat="R1-02")
        self.ada = PrepStudent.objects.create(exam=self.exam, copy_no=1, sciper=123456, first_name="Ada",
                                              last_name="Lovelace", email="ada.lovelace@epfl.ch", section="MX",
                                              room="CO_1", seat="R1-01")
        PrepStudent.objects.create(exam=create_mock_exam(code="OTHER"), copy_no=1, sciper=999999, first_name="F",
                                   last_name="Other", seat="")

    def test_rows_in_id_order(self):
        self.assertEqual(build_students_csv(self.exam), (
            "ID,SCIPER,NAME,LASTNAME,FIRSTNAME,EMAIL,SECTION,ROOM,SEAT\n"
            "1,123456,Ada Lovelace,Lovelace,Ada,ada.lovelace@epfl.ch,MX,CO_1,R1-01\n"
            "2,234567,Alan Turing,Turing,Alan,,,,R1-02\n"
        ))

    def test_written_in_the_project(self):
        with tempfile.TemporaryDirectory() as project_path:
            path = write_students_csv(self.exam, project_path)

            self.assertEqual(path, Path(project_path) / "students.csv")
            self.assertTrue(path.read_text(encoding="utf-8").startswith("ID,SCIPER,NAME,"))

    def test_problems(self):
        self.assertEqual(students_csv_problems(self.exam), [])

        self.ada.needs_correction = True
        self.ada.seat = ""
        self.ada.room = "CO 1, A"
        self.ada.copy_no = 3
        self.ada.save()

        problems = students_csv_problems(self.exam)
        self.assertEqual(len(problems), 4)
        self.assertIn("1 student(s) of the Students page must be corrected", problems[0])
        self.assertIn("1 student(s) of the Students page have no seat", problems[1])
        self.assertIn("without gaps", problems[2])
        self.assertEqual(problems[3], "Student ID 3 (SCIPER 123456): no comma or double quote allowed in room.")
        with self.assertRaises(StudentsCsvError):
            build_students_csv(self.exam)

    def test_no_students(self):
        self.assertIn("no students", students_csv_problems(create_mock_exam(code="EMPTY"))[0])

    def test_students_change_the_source_hash(self):
        before = compute_exam_source_hash(self.exam)
        self.ada.seat = "R1-03"
        self.ada.save()

        self.assertNotEqual(compute_exam_source_hash(self.exam), before)
