import re
import tempfile
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from django.utils import timezone

from examc_app.models import ExamAMCJob, PrepScoringFormula
from examc_app.tasks import update_amc_scoring_task
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user
from examc_app.tests.helpers.prep import PrepViewsTestCase
from examc_app.utils.amc import amc_build_functions as build
from examc_app.utils.amc.amc_build_functions import AmcStepError
from examc_app.utils.preparation_latex_functions import update_exam_latex, update_exam_scoring_latex

START = "examc_app.views.preparation.scoring.update_amc_scoring_task.apply_async"


class FakeAsyncResult:
    state = "PROGRESS"

    def __init__(self, task_id):
        self.task_id = task_id


class ScoringFormulaFormMixin:
    def save_formula(self, formula="b=2,m=-1", **level):
        data = {"form-TOTAL_FORMS": 1, "form-INITIAL_FORMS": 0, "form-MIN_NUM_FORMS": 0, "form-MAX_NUM_FORMS": 1000,
                "prep_section": "", "prep_question": "", "prep_answer": "", **level,
                "form-0-formula": formula, "form-0-question_type": self.types["SCQ"].pk}
        return self.client.post(self.url("scoring_formulas_modal"), data)


class ScoringOfAFinalExamTestCase(ScoringFormulaFormMixin, PrepViewsTestCase):
    """The formulas can be changed at any time: they do not change the layout. AMC then updates its marking scale."""

    def setUp(self):
        super().setUp()
        self.question("SCQ")
        update_exam_latex(self.exam, pages_per_copy=4)

    def start(self, run):
        with patch(START) as apply_async:
            apply_async.return_value = SimpleNamespace(id="task-1")
            response = run()
        return response, apply_async

    def test_saving_on_a_final_exam_starts_the_update_of_the_marking_scale_of_amc(self):
        self.lock()

        response, apply_async = self.start(self.save_formula)

        job = ExamAMCJob.objects.get(exam=self.exam, job_type="scoring_update")
        self.assertEqual((response.status_code, response.json()["success"]), (200, True))
        self.assertEqual(response.json()["scoring_update"],
                         {"job_id": job.pk, "status_url": self.url("scoring_update_status", job_pk=job.pk)})
        self.assertEqual((job.status, job.requested_by, job.celery_task_id), ("pending", self.user, "task-1"))
        apply_async.assert_called_once_with(args=[job.pk], queue="celery", routing_key="celery")
        self.assertEqual(PrepScoringFormula.objects.get(exam=self.exam).formula, "b=2,m=-1")

    def test_deleting_on_a_final_exam_starts_it_too(self):
        formula = PrepScoringFormula.objects.create(exam=self.exam, formula="b=1", question_type=self.types["SCQ"])
        self.lock()

        response, apply_async = self.start(lambda: self.client.post(self.url("delete_scoring_formula", pk=formula.pk)))

        self.assertEqual(response.status_code, 200)
        self.assertIn("scoring_update", response.json())
        apply_async.assert_called_once()
        self.assertFalse(PrepScoringFormula.objects.exists())

    def test_an_exam_that_is_not_final_only_gets_its_latex_rewritten(self):
        response, apply_async = self.start(self.save_formula)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("scoring_update", response.json())
        apply_async.assert_not_called()
        self.assertFalse(ExamAMCJob.objects.filter(job_type="scoring_update").exists())
        self.assertIn("\\baremeDefautS{b=2,m=-1}", (self.project_path() / "global_scoring.tex").read_text())

    def test_the_other_actions_of_a_final_exam_are_still_refused(self):
        self.lock()

        response = self.client.post(self.url("add_prep_section"))

        self.assertEqual(response.status_code, 403)

    def test_a_generation_running_refuses_the_change(self):
        ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type="final_build", status="running",
                                  celery_task_id="task-9")

        with patch("celery.result.AsyncResult", FakeAsyncResult):
            response, apply_async = self.start(self.save_formula)

        self.assertEqual(response.status_code, 403)
        self.assertIn("final generation", response.content.decode())
        apply_async.assert_not_called()
        self.assertFalse(PrepScoringFormula.objects.exists())

    def test_an_update_running_refuses_the_change_until_it_ends(self):
        self.lock()
        job = ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type="scoring_update",
                                        status="running")

        response, apply_async = self.start(self.save_formula)

        self.assertEqual(response.status_code, 403)
        self.assertIn("marking scale", response.content.decode())
        apply_async.assert_not_called()

        job.status = "success"
        job.save()
        response, apply_async = self.start(self.save_formula)

        self.assertEqual(response.status_code, 200)
        apply_async.assert_called_once()

    def test_an_update_that_never_ended_stops_refusing_after_30_minutes(self):
        job = ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type="scoring_update",
                                        status="running")
        ExamAMCJob.objects.filter(pk=job.pk).update(created_at=timezone.now() - timedelta(minutes=31))

        response, _ = self.start(self.save_formula)

        self.assertEqual(response.status_code, 200)
        job.refresh_from_db()
        self.assertEqual((job.status, job.error_message), ("error", "The update was interrupted."))

    def scoring_button(self, html) -> str:
        return re.search(r'<button[^>]*id="openScoringFormulasModal"[^>]*>', html, flags=re.S).group(0)

    def test_the_scoring_buttons_stay_enabled_on_a_final_exam(self):
        question = self.question("SCQ", 2)
        self.lock()

        question_page = self.client.get(self.url("prep_question_panel", question_id=question.pk)).content.decode()
        answer_page = self.client.get(
            self.url("prep_answer_panel", answer_id=question.prepAnswers.first().pk)).content.decode()
        exam_page = self.client.get(self.url("exam_preparation")).content.decode()

        for page in (question_page, answer_page, exam_page):
            self.assertNotIn("disabled", self.scoring_button(page))

    def test_the_scoring_buttons_are_disabled_while_amc_works_on_the_project(self):
        question = self.question("SCQ", 2)
        ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type="scoring_update", status="running")

        page = self.client.get(self.url("prep_question_panel", question_id=question.pk)).content.decode()

        self.assertIn("disabled", self.scoring_button(page))
        self.assertIn("marking scale", self.scoring_button(page))


class ScoringUpdateStatusTestCase(PrepViewsTestCase):
    def job(self, status, job_type="scoring_update", **fields):
        return ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type=job_type, status=status,
                                         **fields)

    def status(self, job):
        return self.client.get(self.url("scoring_update_status", job_pk=job.pk))

    def test_running(self):
        self.assertEqual(self.status(self.job("running")).json(), {"status": "running"})

    def test_success_gives_the_warnings_of_amc(self):
        job = self.job("success", result_json={"warnings": ["AMC: a warning"]})

        self.assertEqual(self.status(job).json(), {"status": "success", "warnings": ["AMC: a warning"]})

    def test_error_gives_the_message(self):
        job = self.job("error", error_message="AMC: the extraction failed")

        self.assertEqual(self.status(job).json(), {"status": "error", "error": "AMC: the extraction failed"})

    def test_the_job_of_another_type_or_of_another_exam_is_not_found(self):
        self.assertEqual(self.status(self.job("running", job_type="exam_preview")).status_code, 404)
        other = ExamAMCJob.objects.create(exam=create_mock_exam(code="OTHER-101"), requested_by=self.user,
                                          job_type="scoring_update", status="running")

        self.assertEqual(self.status(other).status_code, 404)

    def test_needs_the_manage_permission(self):
        job = self.job("running")
        self.client.force_login(create_mock_user(username="nobody", email="nobody@epfl.ch"))

        self.assertEqual(self.status(job).status_code, 403)


class ScoringUpdateTaskTestCase(PrepViewsTestCase):
    def run_task(self, **patches):
        job = ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type="scoring_update",
                                        status="pending")
        latex = patches.pop("latex", MagicMock())
        with patch("examc_app.tasks.update_exam_scoring_latex", latex), \
                patch("examc_app.tasks.update_scoring_in_amc", **patches) as amc:
            update_amc_scoring_task.apply(args=[job.pk])
        job.refresh_from_db()
        return job, latex, amc

    def test_rewrites_the_scoring_files_then_asks_amc(self):
        job, latex, amc = self.run_task(return_value=["AMC: a warning"])

        latex.assert_called_once_with(self.exam)
        amc.assert_called_once_with(self.exam)
        self.assertEqual((job.status, job.result_json), ("success", {"warnings": ["AMC: a warning"]}))

    def test_an_error_of_amc_is_shown(self):
        job, _, _ = self.run_task(side_effect=AmcStepError("AMC: the extraction of the scoring strategy failed."))

        self.assertEqual((job.status, job.error_message), ("error", "AMC: the extraction of the scoring strategy failed."))

    def test_an_unexpected_error_gives_a_reference(self):
        with self.assertLogs("celery_progress.backend", level="ERROR"):
            job, _, _ = self.run_task(side_effect=RuntimeError("boom"))

        self.assertEqual(job.status, "error")
        self.assertRegex(job.error_message, r"^An error occurred while updating the scoring in AMC\. Reference: AMC-[0-9A-F]{8}$")

    def test_a_failure_of_the_latex_does_not_reach_amc(self):
        with self.assertLogs("celery_progress.backend", level="ERROR"):
            job, _, amc = self.run_task(latex=MagicMock(side_effect=ValueError("no template")), return_value=[])

        self.assertEqual(job.status, "error")
        amc.assert_not_called()


class ScoringOnlyLatexTestCase(ScoringFormulaFormMixin, PrepViewsTestCase):
    """For an exam whose final files exist: only the scoring is rewritten, not the first page nor the pages per copy."""

    def test_only_the_scoring_files_change(self):
        question = self.question("SCQ")
        update_exam_latex(self.exam, pages_per_copy=4)
        project = self.project_path()
        untouched = {name: (project / name).read_text() for name in ("first_page.tex", "exam.tex", "examc_generated_vars.tex",
                                                                     "section_header_1.tex")}
        PrepScoringFormula.objects.create(exam=self.exam, formula="b=2,m=-1", question_type=self.types["SCQ"])
        PrepScoringFormula.objects.create(exam=self.exam, formula="b=7", prep_question=question)

        update_exam_scoring_latex(self.exam)

        self.assertEqual({name: (project / name).read_text() for name in untouched}, untouched)
        self.assertIn("\\baremeDefautS{b=2,m=-1}", (project / "global_scoring.tex").read_text())
        self.assertIn("\\bareme{b=7}", (project / "section_1.tex").read_text())
        self.assertIn("\\TotalPagesPerCopy}{4}", untouched["examc_generated_vars.tex"])

    def test_the_whole_update_would_have_reset_the_pages_per_copy(self):
        """Why the scoring has its own update: update_exam_latex does not know the pages per copy of a final exam."""
        self.question("SCQ")
        update_exam_latex(self.exam, pages_per_copy=4)
        project = self.project_path()

        update_exam_latex(self.exam)

        self.assertNotIn("\\TotalPagesPerCopy}{4}", (project / "examc_generated_vars.tex").read_text())


class UpdateScoringInAmcTestCase(SimpleTestCase):
    """The step of AMC: only the marking scale is extracted again, the layout is read to know the pages."""

    def run_update(self, pages, step=None):
        calls = []

        def fake_step(command, cwd, timeout, label):
            calls.append((command, timeout, label))
            return step(command) if step else []

        layout_db = MagicMock()
        layout_db.__enter__.return_value.select_count_layout_pages.return_value = pages
        with tempfile.TemporaryDirectory() as project, tempfile.TemporaryDirectory() as amc_tmp:
            (Path(project) / "exam.tex").write_text("\\documentclass{article}")
            (Path(project) / "amc-compiled.pdf").write_text("pdf")
            with patch.object(build, "get_amc_project_path", return_value=project), \
                    patch.object(build, "_run_amc_step", side_effect=fake_step), \
                    patch.object(build, "AmcLayoutDbManager", return_value=layout_db), \
                    patch.object(build.settings, "AMC_TMP_ROOT", amc_tmp):
                result = build.update_scoring_in_amc(SimpleNamespace(pk=1))
        return result, calls

    def test_runs_the_extraction_of_the_marking_scale_and_nothing_else(self):
        result, calls = self.run_update(pages=1856, step=lambda command: ["AMC: a warning"])

        self.assertEqual(result, ["AMC: a warning"])
        self.assertEqual(len(calls), 1)
        command, timeout, label = calls[0]
        self.assertEqual(command[:4], ["auto-multiple-choice", "prepare", "--mode", "b"])
        self.assertNotIn("meptex", command)
        # The time allowed follows the pages of the layout
        self.assertGreaterEqual(timeout, 1856)

    def test_the_sources_are_copied_without_the_generated_documents(self):
        seen = []

        def step(command):
            seen.extend(sorted(path.name for path in Path(command[-1]).parent.iterdir()))
            return []

        self.run_update(pages=4, step=step)

        self.assertEqual(seen, ["exam.tex"])

    def test_an_exam_whose_layout_is_not_in_amc_is_explained(self):
        with self.assertRaisesMessage(AmcStepError, "generate the final files again"):
            self.run_update(pages=0)

    def test_a_layout_database_that_cannot_be_read_is_explained_too(self):
        from examc_app.exceptions.amc import AmcDbManagerError

        with patch.object(build, "AmcLayoutDbManager", side_effect=AmcDbManagerError("no such table")), \
                patch.object(build, "get_amc_project_path", return_value="/nowhere"):
            with self.assertRaisesMessage(AmcStepError, "generate the final files again"):
                build.update_scoring_in_amc(SimpleNamespace(pk=1))
