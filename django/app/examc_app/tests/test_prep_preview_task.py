from unittest.mock import patch

from django.test import TestCase

from examc_app.models import ExamAMCJob
from examc_app.tasks import compile_exam_preview_task
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user


class PreviewTaskTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()
        self.job = ExamAMCJob.objects.create(exam=self.exam, requested_by=create_mock_user(), job_type="preview",
                                             status="pending")

    def run_task(self, **patches):
        with patch("examc_app.tasks.compile_exam_preview", **patches):
            compile_exam_preview_task.apply(args=[self.job.pk])
        self.job.refresh_from_db()

    def test_success(self):
        self.run_task(return_value={"ok": True, "pdf_path": "/tmp/exam.pdf"})

        self.assertEqual(self.job.status, "success")
        self.assertEqual(self.job.pdf_path, "/tmp/exam.pdf")

    def test_compilation_error_is_shown(self):
        self.run_task(return_value={"ok": False, "error": "Undefined control sequence"})

        self.assertEqual(self.job.status, "error")
        self.assertEqual(self.job.error_message, "Undefined control sequence")

    def test_exception_gives_a_reference_instead_of_a_python_error(self):
        self.run_task(side_effect=RuntimeError("boom"))

        self.assertEqual(self.job.status, "error")
        self.assertRegex(self.job.error_message, r"^An error occurred while generating the exam\. Reference: AMC-[0-9A-F]{8}$")
