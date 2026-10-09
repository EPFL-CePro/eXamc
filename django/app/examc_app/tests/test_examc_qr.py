import tempfile
from datetime import date
from pathlib import Path

from django.test import SimpleTestCase, TestCase

from examc_app.tests.helpers.models import create_mock_exam
from examc_app.utils.examc_qr import (
    ScanQr, parse_scan_qr, qr_exam_code, qr_exam_fields, scan_exams, scan_qr_exam_problem,
)
from examc_app.utils.preparation_latex_functions import write_exam_generated_vars


class ParseScanQrTestCase(SimpleTestCase):
    def test_exam_qr_codes(self):
        self.assertEqual(parse_scan_qr("eXamcQRC2,12,MATH-101,20260115,7,3"),
                         ScanQr("7", "3", "12", "MATH-101", "20260115"))
        # Compiled outside eXamc: no exam pk
        self.assertEqual(parse_scan_qr("eXamcQRC2,,MATH-101,20260115,7,03"),
                         ScanQr("7", "03", "", "MATH-101", "20260115"))

    def test_legacy_qr_codes(self):
        self.assertEqual(parse_scan_qr("CePROExamsQRC,7,3"), ScanQr("7", "3"))
        self.assertEqual(parse_scan_qr("eXamcQRC,7,012"), ScanQr("7", "012"))

    def test_other_qr_codes(self):
        for text in ("https://epfl.ch", "OtherQRC,7,3", "xCePROExamsQRC,7,3", "eXamcQRC2,12,MATH-101,7,3",
                     "eXamcQRC2,,,,7,3", "eXamcQRC2,12,MATH-101,,,3", "CePROExamsQRC,7"):
            with self.subTest(text=text):
                self.assertIsNone(parse_scan_qr(text))

    def test_exam_code(self):
        self.assertEqual(qr_exam_code(" math-101(a), b "), "MATH-101-A-B")


class ScanQrExamTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam(code="MATH-101")
        self.exam.date = date(2026, 1, 15)
        self.exam.save()
        self.common = create_mock_exam(code="PHYS-101")
        self.common.date = None
        self.common.save()
        self.exam.common_exams.add(self.common)
        self.other = create_mock_exam(code="CHEM-101")

    def problem(self, text):
        return scan_qr_exam_problem(parse_scan_qr(text), scan_exams(self.exam))

    def test_generated_by_examc(self):
        self.assertIsNone(self.problem(f"eXamcQRC2,{self.exam.pk},MATH-101,20260115,1,1"))
        self.assertIsNone(self.problem(f"eXamcQRC2,{self.common.pk},PHYS-101,,1,1"))
        self.assertEqual(self.problem(f"eXamcQRC2,{self.other.pk},CHEM-101,20260115,1,1"),
                         "page of another exam (CHEM-101 of 20260115)")

    def test_compiled_outside_examc(self):
        self.assertIsNone(self.problem("eXamcQRC2,,MATH-101,20260115,1,1"))
        self.assertIsNone(self.problem("eXamcQRC2,,MATH-101,,1,1"))
        # The common exam has no date
        self.assertIsNone(self.problem("eXamcQRC2,,PHYS-101,20250610,1,1"))
        # Same course, another session
        self.assertIsNotNone(self.problem("eXamcQRC2,,MATH-101,20250610,1,1"))
        self.assertIsNotNone(self.problem("eXamcQRC2,,CHEM-101,20260115,1,1"))

    def test_legacy_not_checked(self):
        self.assertIsNone(self.problem("CePROExamsQRC,1,1"))

    def test_written_for_latex(self):
        with tempfile.TemporaryDirectory() as project:
            path = write_exam_generated_vars(self.exam, project, 3)

            self.assertEqual(Path(path).read_text(), (
                "% Auto-generated file - do not edit\n"
                "\\newcommand{\\TotalPagesPerCopy}{3}\n"
                f"\\newcommand{{\\ExamcQRExam}}{{eXamcQRC2,{self.exam.pk},MATH-101,20260115}}\n"
            ))
        self.assertEqual(qr_exam_fields(self.common), f"eXamcQRC2,{self.common.pk},PHYS-101,")
