import sqlite3
import time
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, TestCase, override_settings

from examc_app.models import AcademicYear, Exam, PagesGroup, Semester
from examc_app.utils.amc_db_queries import get_amc_copy_nr
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.review_functions import get_copies_pages_by_group, get_exam_scans_dir

# Students list of the AMC project: AMC numbers the copies 1, 2, 3... in its order, the QR codes hold the IDs
ASSOCIATIONS = [(1, "9912"), (2, "0032"), (3, "1122"), (4, "0001"), (5, "1234")]


def write_layout(data_dir, associations=ASSOCIATIONS, question_pages=None):
    """layout.sqlite of an AMC project: the pre-association and the page of question OPEN-Q1 of each copy."""
    data_dir.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(data_dir / "layout.sqlite") as layout:
        layout.execute("CREATE TABLE layout_association (student INTEGER, id TEXT, filename TEXT)")
        layout.executemany("INSERT INTO layout_association VALUES (?, ?, '')", associations)
        layout.execute("CREATE TABLE layout_question (question INTEGER, name TEXT)")
        layout.execute("INSERT INTO layout_question VALUES (1, 'OPEN-Q1')")
        layout.execute("CREATE TABLE layout_box (student INTEGER, page INTEGER, role INTEGER, question INTEGER)")
        for copy_nr, page in (question_pages or {}).items():
            layout.execute("INSERT INTO layout_box VALUES (?, ?, 1, 1)", (copy_nr, page))


class AmcCopyNrTestCase(SimpleTestCase):
    def test_ids_of_the_qr_codes(self):
        with TemporaryDirectory() as data_dir:
            write_layout(Path(data_dir))

            self.assertEqual(get_amc_copy_nr(data_dir, "9912"), 1)
            # Review copy directories are zero-padded, the QR codes lose the leading zeros: '0032' = '32'
            self.assertEqual(get_amc_copy_nr(data_dir, "32"), 2)
            self.assertEqual(get_amc_copy_nr(data_dir, "0001"), 4)
            self.assertEqual(get_amc_copy_nr(data_dir, 1), 4)

    def test_without_association_the_review_copy_is_the_amc_copy(self):
        with TemporaryDirectory() as data_dir:
            self.assertEqual(get_amc_copy_nr(data_dir, "0007"), 7)
            write_layout(Path(data_dir), associations=[])
            self.assertEqual(get_amc_copy_nr(data_dir, "0007"), 7)

    def test_unknown_id(self):
        with TemporaryDirectory() as data_dir:
            write_layout(Path(data_dir))

            self.assertEqual(get_amc_copy_nr(data_dir, "4321"), 4321)

    def test_project_prepared_again(self):
        with TemporaryDirectory() as data_dir:
            write_layout(Path(data_dir))
            self.assertEqual(get_amc_copy_nr(data_dir, "9912"), 1)

            time.sleep(0.01)
            (Path(data_dir) / "layout.sqlite").unlink()
            write_layout(Path(data_dir), associations=[(1, "5555"), (2, "9912")])
            self.assertEqual(get_amc_copy_nr(data_dir, "9912"), 2)


class CopiesPagesByGroupTestCase(TestCase):
    def test_pages_of_copies_numbered_by_id(self):
        exam = Exam.objects.create(code="CS-119(d)", name="Exam", date=date(2026, 10, 30),
                                   semester=Semester.objects.create(code=1, name="Autumn"),
                                   year=AcademicYear.objects.create(code="2026-2027", name="2026-2027"))
        pages_group = PagesGroup.objects.create(exam=exam, group_name="OPEN-Q1", nb_pages=1)

        with TemporaryDirectory() as amc_root, TemporaryDirectory() as scans_root, \
                override_settings(AMC_PROJECTS_ROOT=amc_root, SCANS_ROOT=scans_root):
            # Copy 2 (ID 0032) has its question on page 3, the others on page 2
            write_layout(Path(get_amc_project_path(exam, True)) / "data",
                         question_pages={1: 2, 2: 3, 3: 2, 4: 2, 5: 2})
            for _, row_id in ASSOCIATIONS:
                copy_dir = get_exam_scans_dir(exam) / row_id
                copy_dir.mkdir(parents=True)
                for page in range(1, 5):
                    (copy_dir / f"copy_{row_id}_{page:02d}.jpg").write_bytes(b"scan")

            pages = get_copies_pages_by_group(pages_group)

        self.assertEqual([(p["copy_no"], p["page_no"]) for p in pages],
                         [("0001", "02"), ("0032", "03"), ("1122", "02"), ("1234", "02"), ("9912", "02")])
