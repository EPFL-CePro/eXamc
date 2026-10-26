from unittest.mock import MagicMock, patch

from pypdf import PdfWriter

from examc_app.models import Exam, ExamAMCJob, ExamBuild
from examc_app.tasks import generate_final_exam_files_task
from examc_app.tests.helpers.prep import PrepViewsTestCase
from examc_app.tests.test_prep_layout_files import all_pages, xy_text
from examc_app.utils.amc.amc_build_functions import AmcStepError


class FinalGenerationTaskTestCase(PrepViewsTestCase):
    """What the task does with the build and with AMC (the compilations and AMC itself are simulated)."""

    COPIES, PAGES = 2, 2

    def setUp(self):
        super().setUp()
        patcher = patch("examc_app.tasks.ProgressRecorder", MagicMock())
        patcher.start()
        self.addCleanup(patcher.stop)

        self.job = ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type="final_build",
                                             status="pending")

    def build(self, pdf_pages=None, status="ready") -> ExamBuild:
        """A build whose project holds the subject PDF and the XY file of COPIES copies of PAGES pages."""
        project = self.project_path()
        pdf = project / f"{self.exam.code}-sujet.pdf"
        writer = PdfWriter()
        for _ in range(pdf_pages or self.COPIES * self.PAGES):
            writer.add_blank_page(width=595, height=842)
        with open(pdf, "wb") as handle:
            writer.write(handle)
        xy = project / f"{self.exam.code}-calage.xy"
        xy.write_text(xy_text(*all_pages(self.COPIES, self.PAGES)), encoding="utf-8")

        return ExamBuild.objects.create(exam=self.exam, version=1, status=status, project_path=str(project),
                                        compiled_pdf_path=str(pdf), xy_path=str(xy), error_message="Compilation failed")

    def run_task(self, build, register=None):
        register = register or MagicMock(return_value=[])
        with patch("examc_app.tasks.build_final_exam", return_value=build), \
                patch("examc_app.tasks.register_exam_in_amc", register):
            result = generate_final_exam_files_task.apply(args=[self.job.pk])
        self.job.refresh_from_db()
        self.exam = Exam.objects.get(pk=self.exam.pk)
        build.refresh_from_db()
        return result, register

    def test_success_registers_the_exam_in_amc_then_finalizes_it(self):
        build = self.build()

        result, register = self.run_task(build, MagicMock(return_value=["AMC: a warning"]))

        self.assertTrue(result.successful())
        register.assert_called_once()
        self.assertEqual(register.call_args.args[1], build.xy_path)
        self.assertEqual(register.call_args.kwargs["expected_pages"], 4)
        self.assertEqual(self.job.status, "success")
        self.assertEqual(self.job.result_json["warnings"], ["AMC: a warning"])
        self.assertEqual(self.job.result_json["summary"], {"copies": 2, "pages_per_copy": 2, "pages": 4})
        self.assertTrue(self.exam.is_finalized)
        self.assertEqual(self.exam.finalized_build_id, build.pk)

    def test_the_warnings_of_the_build_come_with_those_of_amc(self):
        build = self.build()
        build.build_warnings = ["1 copy has more than 2 pages"]

        self.run_task(build, MagicMock(return_value=["AMC: a warning"]))

        self.assertEqual(self.job.result_json["warnings"], ["1 copy has more than 2 pages", "AMC: a warning"])

    def test_booklet_with_a_number_of_pages_that_is_not_a_multiple_of_4_is_warned(self):
        self.exam.print_format = Exam.PRINT_FORMAT_BOOKLET
        self.exam.save()

        self.run_task(self.build())

        self.assertTrue(any("multiple of 4" in warning for warning in self.job.result_json["warnings"]))

    def test_an_error_of_amc_fails_the_generation_and_the_build_and_is_shown(self):
        build = self.build()
        error = AmcStepError("AMC: the layout detection failed. No src file")

        result, _ = self.run_task(build, MagicMock(side_effect=error))

        self.assertTrue(result.failed())
        self.assertEqual((self.job.status, self.job.error_message), ("error", str(error)))
        self.assertEqual((build.status, build.error_message), ("error", str(error)))
        self.assertFalse(self.exam.is_finalized)

    def test_pages_of_the_pdf_and_of_the_layout_file_must_match(self):
        build = self.build(pdf_pages=3)

        result, register = self.run_task(build)

        self.assertTrue(result.failed())
        register.assert_not_called()
        self.assertIn("PDF/XY page mismatch: PDF=3 XY=4", self.job.error_message)
        self.assertEqual(build.status, "error")
        self.assertFalse(self.exam.is_finalized)

    def test_a_build_that_failed_is_not_registered_in_amc(self):
        build = self.build(status="error")

        result, register = self.run_task(build)

        self.assertTrue(result.failed())
        register.assert_not_called()
        self.assertEqual((self.job.status, self.job.error_message), ("error", "Compilation failed"))
        self.assertFalse(self.exam.is_finalized)
