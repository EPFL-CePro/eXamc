import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from examc_app.models import ExamAMCJob
from examc_app.tests.helpers.models import create_mock_user
from examc_app.tests.helpers.prep import PrepViewsTestCase


class PreviewViewsTestCase(PrepViewsTestCase):
    def job(self, status="pending", user=None, **fields):
        return ExamAMCJob.objects.create(exam=self.exam, requested_by=user or self.user, job_type="exam_preview",
                                         status=status, **fields)

    def other_user(self):
        return create_mock_user(username="someone-else", email="someone-else@epfl.ch")


class PreviewStartTestCase(PreviewViewsTestCase):
    def start(self):
        with patch("examc_app.views.preparation.preview.compile_exam_preview_task.apply_async") as apply_async, \
                patch("examc_app.views.preparation.preview.delete_exam_preview_job_files") as delete_files:
            apply_async.return_value = SimpleNamespace(id="task-7")
            response = self.client.post(self.url("exam_preview_start"))
        return response, apply_async, delete_files

    def test_creates_a_job_and_starts_the_task(self):
        response, apply_async, _ = self.start()

        job = ExamAMCJob.objects.get(exam=self.exam)
        self.assertEqual((job.job_type, job.status, job.requested_by, job.celery_task_id),
                         ("exam_preview", "pending", self.user, "task-7"))
        self.assertEqual(response.json(), {"job_id": job.pk, "task_id": "task-7", "status": "pending", "reused": False})
        apply_async.assert_called_once_with(args=[job.pk], queue="celery", routing_key="celery")

    def test_replaces_the_previous_previews_of_the_user_only(self):
        previous = self.job(status="running", pdf_path="/tmp/old.pdf")
        someone_else = self.job(status="running", user=self.other_user())

        _, _, delete_files = self.start()

        self.assertFalse(ExamAMCJob.objects.filter(pk=previous.pk).exists())
        delete_files.assert_called_once()
        self.assertEqual(delete_files.call_args.args[0].pk, previous.pk)
        someone_else.refresh_from_db()
        self.assertEqual(someone_else.status, "running")
        self.assertEqual(ExamAMCJob.objects.filter(exam=self.exam).count(), 2)

    def test_the_jobs_of_other_types_are_kept(self):
        final = ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type="final_build",
                                          status="success")

        self.start()

        self.assertTrue(ExamAMCJob.objects.filter(pk=final.pk).exists())


class PreviewStatusTestCase(PreviewViewsTestCase):
    def status(self, job):
        return self.client.get(self.url("exam_preview_status", job_pk=job.pk))

    def test_pending_and_running_only_give_the_status(self):
        self.assertEqual(self.status(self.job("pending")).json(), {"status": "pending"})
        self.assertEqual(self.status(self.job("running")).json(), {"status": "running"})

    def test_success_gives_the_url_of_the_pdf(self):
        job = self.job("success", pdf_path="/tmp/preview.pdf")

        body = self.status(job).json()

        self.assertEqual(body, {"status": "success", "pdf_url": self.url("exam_preview_pdf_file", job_pk=job.pk)})

    def test_error_gives_the_message(self):
        job = self.job("error", error_message="Undefined control sequence")

        self.assertEqual(self.status(job).json(), {"status": "error", "error": "Undefined control sequence"})

    def test_the_job_of_another_user_is_not_found(self):
        job = self.job("success", user=self.other_user())

        self.assertEqual(self.status(job).status_code, 404)


class PreviewFileTestCase(PreviewViewsTestCase):
    def setUp(self):
        super().setUp()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.pdf = Path(folder.name) / "preview.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 preview")

    def fetch(self, job):
        return self.client.get(self.url("exam_preview_pdf_file", job_pk=job.pk))

    def test_serves_the_pdf_of_a_successful_job(self):
        response = self.fetch(self.job("success", pdf_path=str(self.pdf)))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertEqual(b"".join(response.streaming_content), b"%PDF-1.4 preview")

    def test_a_job_that_is_not_successful_has_no_pdf(self):
        for status in ("pending", "running", "error"):
            with self.subTest(status=status):
                self.assertEqual(self.fetch(self.job(status, pdf_path=str(self.pdf))).status_code, 404)

    def test_a_missing_file_is_not_found(self):
        self.pdf.unlink()

        self.assertEqual(self.fetch(self.job("success", pdf_path=str(self.pdf))).status_code, 404)

    def test_a_successful_job_without_a_path_is_not_found(self):
        self.assertEqual(self.fetch(self.job("success", pdf_path="")).status_code, 404)

    def test_the_pdf_of_another_user_is_not_found(self):
        job = self.job("success", pdf_path=str(self.pdf), user=self.other_user())

        self.assertEqual(self.fetch(job).status_code, 404)
