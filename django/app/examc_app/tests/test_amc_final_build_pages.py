import re
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from examc_app.models import Exam, PrepStudent
from examc_app.tests.helpers.models import create_mock_exam
from examc_app.utils.amc.amc_build_functions import (
    _ensure_xy_output, build_final_exam, longer_copies_warning, read_copy_pages_from_log, round_pages_per_copy)
from examc_app.utils.preparation_functions import create_prep_section
from examc_app.utils.preparation_latex_functions import update_exam_latex


class PagesHelpersTestCase(SimpleTestCase):
    def test_copy_pages_are_read_from_the_log(self):
        log = "(./first_page.tex)\nEXAMC-COPY-PAGES=7\n[1] [2]\nEXAMC-COPY-PAGES=8\nOther line EXAMC-COPY-PAGES=9\n"

        self.assertEqual(read_copy_pages_from_log(log), [7, 8])
        self.assertEqual(read_copy_pages_from_log(""), [])

    def test_booklet_pages_are_a_multiple_of_4(self):
        self.assertEqual([round_pages_per_copy(pages, True) for pages in (1, 4, 5, 7, 8)], [4, 4, 8, 8, 8])
        self.assertEqual(round_pages_per_copy(7, False), 7)

    def test_warning_tells_which_copies_and_why(self):
        warning = longer_copies_warning([7, 8, 7, 8], estimated=7, final=8, shuffled=True, booklet=False)

        self.assertEqual(warning, (
            "2 copies have more than 7 pages (copy 2, 4) because the questions or the answers are in random "
            "order, so the length of the copies varies. All the copies were padded with blank pages to 8 pages, "
            "which needed a second compilation of the subject."))

    def test_warning_lists_at_most_some_copies(self):
        warning = longer_copies_warning([9] * 12, estimated=8, final=12, shuffled=False, booklet=True, max_listed=3)

        self.assertIn("12 copies have more than 8 pages (copy 1, 2, 3 and 9 others)", warning)
        self.assertIn("longer than the one of the catalog copy", warning)
        self.assertIn("12 pages (a multiple of 4 for the booklet)", warning)

    def test_xy_of_the_last_compilation_is_used(self):
        with tempfile.TemporaryDirectory() as workspace:
            workspace = Path(workspace)
            (workspace / "calage.xy").write_text("first compilation")
            (workspace / "amc-compiled.xy").write_text("second compilation")

            self.assertEqual(_ensure_xy_output(workspace).read_text(), "second compilation")


class FinalBuildPagesTestCase(TestCase):
    """build_final_exam with fake compilations: the catalog copy has `catalog_pages`, the copies `copy_pages` at
    each subject compilation."""

    def setUp(self):
        roots = tempfile.TemporaryDirectory()
        self.addCleanup(roots.cleanup)
        override = override_settings(AMC_PROJECTS_ROOT=f"{roots.name}/projects", AMC_TMP_ROOT=f"{roots.name}/tmp")
        override.enable()
        self.addCleanup(override.disable)

        self.exam = create_mock_exam()
        self.exam.duration = "2h"
        self.exam.save()
        create_prep_section(self.exam)
        for copy_no in (1, 2):
            PrepStudent.objects.create(exam=self.exam, copy_no=copy_no, sciper=100000 + copy_no, first_name="Ada",
                                       last_name=f"Lovelace{copy_no}", seat=f"A{copy_no}")
        # Creates the AMC project, as the creation of the exam
        update_exam_latex(self.exam)
        self.compilations = []

    def build(self, catalog_pages, copy_pages):
        def compile_exam_in_workspace(workspace_path, *, timeout, latex_engine, mode, on_page=None):
            generated_vars = (workspace_path / "examc_generated_vars.tex").read_text()
            total = int(re.search(r"\\TotalPagesPerCopy\}\{(\d+)\}", generated_vars).group(1))
            self.compilations.append((mode, total))
            pages = [catalog_pages] if mode == "catalog" else copy_pages
            log = "".join(f"EXAMC-COPY-PAGES={copy}\n" for copy in pages)
            return {"ok": True, "build_log": log, "xy_path": str(workspace_path / "calage.xy")}

        def promote_workspace_to_project(*, workspace_path, persistent_project_path, exam):
            return {"project_path": persistent_project_path}

        with patch("examc_app.utils.amc.amc_build_functions.compile_exam_in_workspace", compile_exam_in_workspace), \
                patch("examc_app.utils.amc.amc_build_functions.promote_workspace_to_project",
                      promote_workspace_to_project):
            return build_final_exam(self.exam)

    def test_one_subject_compilation_when_the_copies_have_the_pages_of_the_catalog(self):
        build = self.build(catalog_pages=7, copy_pages=[7, 6])

        self.assertEqual(build.status, "ready", build.error_message)
        self.assertEqual(self.compilations, [("catalog", 2), ("subject", 7)])
        self.assertEqual(build.build_warnings, [])

    def test_compiled_again_with_a_warning_when_some_copies_are_longer(self):
        self.exam.prepSections.update(random_questions=True)

        build = self.build(catalog_pages=7, copy_pages=[7, 8])

        self.assertEqual(self.compilations, [("catalog", 2), ("subject", 7), ("subject", 8)])
        self.assertEqual(len(build.build_warnings), 1)
        self.assertIn("1 copy has more than 7 pages (copy 2) because the questions or the answers are in random "
                      "order", build.build_warnings[0])

    def test_compiled_again_without_warning_when_all_the_copies_are_shorter(self):
        build = self.build(catalog_pages=8, copy_pages=[7, 7])

        self.assertEqual(self.compilations, [("catalog", 2), ("subject", 8), ("subject", 7)])
        self.assertEqual(build.build_warnings, [])

    def test_booklet_rounds_the_pages_before_comparing(self):
        self.exam.print_format = Exam.PRINT_FORMAT_BOOKLET
        self.exam.save()

        build = self.build(catalog_pages=7, copy_pages=[7, 8])

        self.assertEqual(self.compilations, [("catalog", 2), ("subject", 8)])
        self.assertEqual(build.build_warnings, [])
