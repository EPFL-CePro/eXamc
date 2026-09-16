from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import TestCase, override_settings

from examc_app.models import (
    AcademicYear,
    Exam,
    PageMarkers,
    PagesGroup,
    PagesGroupGradingSchemeCheckedBox,
    Semester,
)
from examc_app.utils.dashboard import _add_manage_todos, _get_pages_group_progress, _get_review_progress


class DashboardReviewProgressTestCase(TestCase):
    def setUp(self):
        self.scans_root = TemporaryDirectory()
        self.addCleanup(self.scans_root.cleanup)
        self.settings_override = override_settings(SCANS_ROOT=self.scans_root.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)

        self.year = AcademicYear.objects.create(code="2025-2026", name="2025-2026")
        self.semester = Semester.objects.create(code=1, name="Autumn")
        self.exam = Exam.objects.create(
            code="TEST-EXAM",
            name="Test Exam",
            semester=self.semester,
            year=self.year,
            date=date(2026, 1, 20),
        )

    def create_scan_copies(self, *copy_numbers):
        scans_path = (
            Path(self.scans_root.name)
            / self.year.code
            / str(self.semester.code)
            / f"{self.exam.code}_{self.exam.date:%Y%m%d}"
        )
        for copy_number in copy_numbers:
            (scans_path / copy_number).mkdir(parents=True, exist_ok=True)
        return scans_path

    def create_scan_file(self, copy_number, filename):
        scans_path = self.create_scan_copies(copy_number)
        scan_file = scans_path / copy_number / filename
        scan_file.write_bytes(b"scan")
        return scan_file

    def test_pages_group_progress_uses_review_summary_copy_count(self):
        self.create_scan_copies("0000", "0001", "0002", "0003", "0004")
        pages_group = PagesGroup.objects.create(
            exam=self.exam,
            group_name="Q1",
            nb_pages=1,
        )
        for copy_no in ("0001", "0002"):
            PageMarkers.objects.create(
                copie_no=copy_no,
                page_no="01",
                pages_group=pages_group,
                filename=f"{copy_no}_01.jpg",
                markers='{"markers":[{"typeName":"HighlightMarker"}]}',
                exam=self.exam,
                correctorBoxMarked=True,
            )
        PageMarkers.objects.create(
            copie_no="0003",
            page_no="01",
            pages_group=pages_group,
            filename="0003_01.jpg",
            markers="",
            exam=self.exam,
            correctorBoxMarked=False,
        )
        PageMarkers.objects.create(
            copie_no="CORR-BOX",
            page_no="0",
            pages_group=pages_group,
            filename="corr-box.jpg",
            markers='{"markers":[{"typeName":"HighlightMarker"}]}',
            exam=self.exam,
            correctorBoxMarked=True,
        )

        progress = _get_pages_group_progress(pages_group)

        self.assertEqual(progress["graded"], 2)
        self.assertEqual(progress["total"], 4)
        self.assertEqual(progress["percent"], 50)

    def test_review_progress_averages_question_progress(self):
        self.create_scan_copies("0001", "0002", "0003", "0004")
        first_group = PagesGroup.objects.create(
            exam=self.exam,
            group_name="Q1",
            nb_pages=1,
        )
        PagesGroup.objects.create(
            exam=self.exam,
            group_name="Q2",
            nb_pages=1,
        )
        for copy_no in ("0001", "0002", "0003", "0004"):
            PageMarkers.objects.create(
                copie_no=copy_no,
                page_no="01",
                pages_group=first_group,
                filename=f"{copy_no}_01.jpg",
                markers='{"markers":[{"typeName":"HighlightMarker"}]}',
                exam=self.exam,
                correctorBoxMarked=True,
            )

        progress = _get_review_progress(self.exam)

        self.assertEqual(progress["graded"], 2)
        self.assertEqual(progress["total"], 4)
        self.assertEqual(progress["percent"], 50)

    def test_grading_scheme_progress_counts_distinct_reviewed_copies(self):
        self.create_scan_copies("0001", "0002", "0003")
        pages_group = PagesGroup.objects.create(
            exam=self.exam,
            group_name="Q1",
            nb_pages=1,
            use_grading_scheme=True,
        )
        PagesGroupGradingSchemeCheckedBox.objects.create(
            pages_group=pages_group,
            copy_nr="0001",
        )
        PagesGroupGradingSchemeCheckedBox.objects.create(
            pages_group=pages_group,
            copy_nr="0001",
        )
        PagesGroupGradingSchemeCheckedBox.objects.create(
            pages_group=pages_group,
            copy_nr="0002",
        )

        progress = _get_pages_group_progress(pages_group)

        self.assertEqual(progress["graded"], 2)
        self.assertEqual(progress["total"], 3)
        self.assertEqual(progress["percent"], 67)

    def test_manage_todos_do_not_report_missing_scans_when_scan_files_exist(self):
        self.exam.review_option = True
        self.exam.save()
        PagesGroup.objects.create(
            exam=self.exam,
            group_name="Q1",
            nb_pages=1,
        )
        self.create_scan_file("0001", "copy_0001_01.jpg")

        todos = []
        _add_manage_todos(todos, self.exam)

        self.assertFalse(any(
            todo["description"] == "Review is enabled but no scanned page is available yet."
            for todo in todos
        ))

    def test_manage_todos_report_missing_scans_when_no_scan_files_exist(self):
        self.exam.review_option = True
        self.exam.save()
        PagesGroup.objects.create(
            exam=self.exam,
            group_name="Q1",
            nb_pages=1,
        )
        self.create_scan_copies("0001")

        todos = []
        _add_manage_todos(todos, self.exam)

        self.assertTrue(any(
            todo["description"] == "Review is enabled but no scanned page is available yet."
            for todo in todos
        ))
