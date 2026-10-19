import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from examc_app.utils.amc import amc_build_functions as build


def python_command(code):
    return [sys.executable, "-c", code]


class RunAmcStepTests(SimpleTestCase):
    """The AMC commands of the final generation: what AMC prints is what the user reads."""

    def run_step(self, code, timeout=30):
        with tempfile.TemporaryDirectory() as tmp:
            return build._run_amc_step(python_command(code), Path(tmp), timeout, "the layout detection")

    def test_warnings_are_returned(self):
        warnings = self.run_step("print('WARN: remove the accents of Q1')")

        self.assertEqual(warnings, ["remove the accents of Q1"])

    def test_errors_of_amc_fail_the_step_even_with_a_zero_exit_code(self):
        with self.assertRaisesMessage(build.AmcStepError, "the layout detection failed. Question Q2 has no answer"):
            self.run_step("print('ERR: Question Q2 has no answer')")

    def test_failure_without_message_shows_the_end_of_the_output(self):
        with self.assertRaisesMessage(build.AmcStepError, "No src file"):
            self.run_step("import sys; print('No src file'); sys.exit(2)")

    def test_timeout(self):
        with self.assertRaisesMessage(build.AmcStepError, "timed out after 1 s"):
            self.run_step("import time; time.sleep(30)", timeout=1)


class RegisterExamInAmcTests(SimpleTestCase):
    def register(self, detected_pages, step=None):
        calls = []

        def fake_step(command, cwd, timeout, label):
            calls.append((command[1:3] if command[1] == "prepare" else command[1], label))
            return step(command) if step else []

        layout_db = MagicMock()
        layout_db.__enter__.return_value.select_count_layout_pages.return_value = detected_pages

        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as amc_tmp:
            (Path(project) / "exam.tex").write_text("\\documentclass{article}")
            (Path(project) / "amc-compiled.pdf").write_text("pdf")
            with patch.object(build, "get_amc_project_path", return_value=project), \
                    patch.object(build, "_run_amc_step", side_effect=fake_step), \
                    patch.object(build, "AmcLayoutDbManager", return_value=layout_db), \
                    patch.object(build.settings, "AMC_TMP_ROOT", amc_tmp):
                result = build.register_exam_in_amc(
                    SimpleNamespace(pk=1), f"{project}/EXAM-calage.xy", expected_pages=8)
            data_dir_exists = (Path(project) / "data").is_dir()
        return result, calls, data_dir_exists

    def test_layout_then_scoring(self):
        warnings, calls, data_dir_exists = self.register(detected_pages=8)

        self.assertEqual(warnings, [])
        self.assertEqual([call[0] for call in calls], ["meptex", ["prepare", "--mode"]])
        self.assertTrue(data_dir_exists)

    def test_page_count_different_from_the_subject_is_an_error(self):
        with self.assertRaisesMessage(build.AmcStepError, "found 6 pages, but the subject has 8"):
            self.register(detected_pages=6)

    def test_warnings_of_both_steps_are_returned(self):
        warnings, _, _ = self.register(detected_pages=8, step=lambda command: [f"warning of {command[1]}"])

        self.assertEqual(warnings, ["warning of meptex", "warning of prepare"])

    def test_scoring_runs_in_a_copy_without_the_generated_documents(self):
        copied = []

        def step(command):
            if command[1] == "prepare":
                sources = Path(command[-1]).parent
                copied.extend(sorted(path.name for path in sources.iterdir()))
            return []

        self.register(detected_pages=8, step=step)

        self.assertEqual(copied, ["exam.tex"])
