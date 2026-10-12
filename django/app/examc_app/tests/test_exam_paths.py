import tempfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from examc_app.exceptions.exam import (
    ExamDateMissingError,
    ExamFolderConflictError,
    ExamFolderNameInvalidError,
)
from examc_app.services.exam.paths import (
    get_exam_amc_project_dir,
    get_exam_amc_project_url,
    get_exam_catalog_dir,
    get_exam_marked_scans_dir,
    get_exam_scans_dir,
    get_exam_subdir,
    update_exam_folders,
)


def make_exam(code="CS-101", year="2025-2026", semester="1", exam_date=date(2026, 1, 9)):
    return SimpleNamespace(
        pk=1, code=code, date=exam_date,
        year=SimpleNamespace(code=year), semester=SimpleNamespace(code=semester),
    )


class ExamSubdirTests(SimpleTestCase):
    def test_format_is_year_semester_code_and_compact_date(self):
        self.assertEqual(get_exam_subdir(make_exam()), "2025-2026/1/CS-101_20260109")

    def test_missing_date_raises(self):
        with self.assertRaises(ExamDateMissingError):
            get_exam_subdir(make_exam(exam_date=None))

    def test_invalid_folder_names_raise(self):
        for bad_code in ("", "  ", "..", "a/b", "../../etc", "a\\b"):
            with self.subTest(code=bad_code), self.assertRaises(ExamFolderNameInvalidError):
                get_exam_subdir(make_exam(code=bad_code))
        with self.assertRaises(ExamFolderNameInvalidError):
            get_exam_subdir(make_exam(year=""))
        with self.assertRaises(ExamFolderNameInvalidError):
            get_exam_subdir(make_exam(semester="1/2"))


class ExamDirsTests(SimpleTestCase):
    def test_each_root_uses_the_same_subdir(self):
        with override_settings(
            SCANS_ROOT=Path("/s"), MARKED_SCANS_ROOT=Path("/m"),
            AMC_PROJECTS_ROOT=Path("/a"), CATALOG_ROOT=Path("/c"), AMC_PROJECTS_URL="/amc_projects/",
        ):
            exam, sub = make_exam(), "2025-2026/1/CS-101_20260109"
            self.assertEqual(get_exam_scans_dir(exam), Path("/s") / sub)
            self.assertEqual(get_exam_marked_scans_dir(exam), Path("/m") / sub)
            self.assertEqual(get_exam_amc_project_dir(exam), Path("/a") / sub)
            self.assertEqual(get_exam_catalog_dir(exam), Path("/c") / sub)
            self.assertEqual(get_exam_amc_project_url(exam), "/amc_projects/" + sub)


class RenameExamFoldersTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.roots = {name: base / name for name in
                      ("SCANS_ROOT", "MARKED_SCANS_ROOT", "AMC_PROJECTS_ROOT", "CATALOG_ROOT")}
        override = override_settings(**self.roots)
        override.enable()
        self.addCleanup(override.disable)

    def make(self, root, subdir, filename="f.txt"):
        folder = self.roots[root] / subdir
        folder.mkdir(parents=True)
        (folder / filename).write_text("x")
        return folder

    def test_moves_every_root_where_the_folder_exists_including_catalogs(self):
        self.make("SCANS_ROOT", "2025-2026/1/A_20260109")
        self.make("CATALOG_ROOT", "2025-2026/1/A_20260109")

        moved = update_exam_folders("2025-2026/1/A_20260109", "2026-2027/2/B_20260210")

        self.assertEqual(len(moved), 2)
        self.assertTrue((self.roots["SCANS_ROOT"] / "2026-2027/2/B_20260210/f.txt").exists())  # new year dir created
        self.assertTrue((self.roots["CATALOG_ROOT"] / "2026-2027/2/B_20260210/f.txt").exists())
        self.assertFalse((self.roots["SCANS_ROOT"] / "2025-2026/1/A_20260109").exists())

    def test_nothing_to_move_is_not_an_error(self):
        self.assertEqual(update_exam_folders("2025-2026/1/A_20260109", "2025-2026/1/A_20260110"), [])

    def test_same_subdir_does_nothing(self):
        self.make("SCANS_ROOT", "2025-2026/1/A_20260109")
        self.assertEqual(update_exam_folders("2025-2026/1/A_20260109", "2025-2026/1/A_20260109"), [])
        self.assertTrue((self.roots["SCANS_ROOT"] / "2025-2026/1/A_20260109").exists())

    def test_conflict_moves_nothing_and_never_nests(self):
        self.make("SCANS_ROOT", "2025-2026/1/A_20260109")
        self.make("AMC_PROJECTS_ROOT", "2025-2026/1/A_20260109")
        self.make("AMC_PROJECTS_ROOT", "2025-2026/1/B_20260109", "other.txt")  # another exam

        with self.assertRaises(ExamFolderConflictError):
            update_exam_folders("2025-2026/1/A_20260109", "2025-2026/1/B_20260109")

        self.assertTrue((self.roots["SCANS_ROOT"] / "2025-2026/1/A_20260109/f.txt").exists())  # untouched
        self.assertFalse((self.roots["AMC_PROJECTS_ROOT"] / "2025-2026/1/B_20260109/A_20260109").exists())
