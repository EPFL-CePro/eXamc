import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from examc_app.models import ExamAMCJob, PrepStudent
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user
from examc_app.utils.amc.amc_build_functions import (
    BuildCancelled, _run_latex, _should_cancel, _report_progress)
from examc_app.utils.preparation_functions import is_exam_locked


class FinalGenerationLockTestCase(TestCase):
    def setUp(self):
        projects_root = tempfile.TemporaryDirectory()
        self.addCleanup(projects_root.cleanup)
        override = override_settings(AMC_PROJECTS_ROOT=projects_root.name)
        override.enable()
        self.addCleanup(override.disable)

        self.exam = create_mock_exam()
        self.user = create_mock_user()
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)

    def start_job(self, status="running"):
        return ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type="final_build",
                                         status=status, celery_task_id="task-1")

    @patch("celery.result.AsyncResult")
    def test_exam_is_locked_while_the_generation_runs(self, async_result):
        async_result.return_value.state = "STARTED"
        self.assertFalse(is_exam_locked(self.exam))

        job = self.start_job()
        self.assertTrue(is_exam_locked(self.exam))

        job.status = "cancelled"
        job.save()
        self.assertFalse(is_exam_locked(self.exam))

    @patch("celery.result.AsyncResult")
    def test_modifications_are_refused_while_the_generation_runs(self, async_result):
        async_result.return_value.state = "STARTED"
        self.start_job()

        response = self.client.post(reverse("add_prep_section", kwargs={"exam_pk": self.exam.pk}))

        self.assertEqual(response.status_code, 403)
        self.assertIn("final generation", response.content.decode())
        self.assertEqual(self.exam.prepSections.count(), 0)

    @patch("celery.result.AsyncResult")
    def test_students_are_locked_while_the_generation_runs(self, async_result):
        async_result.return_value.state = "STARTED"
        student = PrepStudent.objects.create(exam=self.exam, copy_no=1, sciper=123456, first_name="Ada",
                                             last_name="Lovelace", seat="A1")
        self.start_job()

        response = self.client.patch(
            f"/api/exams/{self.exam.pk}/prep-students/{student.pk}/", {"seat": "B2"}, content_type="application/json")

        self.assertEqual(response.status_code, 403)
        student.refresh_from_db()
        self.assertEqual(student.seat, "A1")

    @patch("celery.result.AsyncResult")
    def test_cancel_asks_the_running_task_to_stop(self, async_result):
        async_result.return_value.state = "STARTED"
        job = self.start_job()

        response = self.client.post(reverse("cancel_final_exam_files", kwargs={"exam_pk": self.exam.pk}))

        self.assertEqual(response.json()["cancelling"], True)
        job.refresh_from_db()
        self.assertTrue(job.cancel_requested)
        # The task ends the job itself: the exam stays locked until then
        self.assertEqual(job.status, "running")

    @patch("examc.celery.app.control.revoke")
    def test_cancel_of_a_job_not_started_revokes_it(self, revoke):
        job = self.start_job(status="pending")

        response = self.client.post(reverse("cancel_final_exam_files", kwargs={"exam_pk": self.exam.pk}))

        self.assertEqual(response.json()["status"], "cancelled")
        revoke.assert_called_once_with("task-1")
        job.refresh_from_db()
        self.assertEqual(job.status, "cancelled")
        self.assertFalse(is_exam_locked(self.exam))

    def test_cancel_without_running_generation(self):
        response = self.client.post(reverse("cancel_final_exam_files", kwargs={"exam_pk": self.exam.pk}))

        self.assertEqual(response.status_code, 404)


class BuildCancelTestCase(SimpleTestCase):
    def test_latex_process_is_killed_when_cancelled(self):
        token = _should_cancel.set(lambda: True)
        self.addCleanup(_should_cancel.reset, token)

        with patch("examc_app.utils.amc.amc_build_functions.CANCEL_POLL_SECONDS", 0.05):
            with self.assertRaises(BuildCancelled):
                _run_latex(["sleep", "30"], Path("."), timeout=60)

    def test_steps_are_stopped_when_cancelled(self):
        token = _should_cancel.set(lambda: True)
        self.addCleanup(_should_cancel.reset, token)

        with self.assertRaises(BuildCancelled):
            _report_progress(None, 10, "Compiling")

    def test_nothing_is_stopped_without_cancel(self):
        returncode, output = _run_latex(["echo", "done"], Path("."), timeout=60)

        self.assertEqual((returncode, output), (0, "done\n"))
