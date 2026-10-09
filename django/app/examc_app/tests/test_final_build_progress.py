import sys
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from examc_app.models import ExamAMCJob, PrepStudent
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user
from examc_app.utils.amc import amc_build_functions as build
from examc_app.utils.preparation_functions import get_active_final_build_job

# Prints like pdflatex: package dates, page markers of 2 copies of 2 pages ("[1{map}]" first), then a slow end
FAKE_LATEX = (
    "import sys, time\n"
    "print('(article.cls [2021/10/04 v1.4n Standard LaTeX])')\n"
    "print('[1{/var/lib/texmf/fonts/map/pdftex/updmap/pdftex.map}] [2] [1]')\n"
    "print('[2] (./exam.aux)')\n"
    "sys.stdout.flush()\n"
    "time.sleep(float(sys.argv[1]))\n"
)


class RunLatexTestCase(SimpleTestCase):
    def test_pages_counted_while_compiling(self):
        pages = []
        with tempfile.TemporaryDirectory() as tmp:
            returncode, output = build._run_latex([sys.executable, "-c", FAKE_LATEX, "0"], Path(tmp), 30, pages.append)

        self.assertEqual(returncode, 0)
        # The package date is not a page
        self.assertEqual(pages, [3, 4])
        self.assertIn("exam.aux", output)

    def test_timeout_kills(self):
        with tempfile.TemporaryDirectory() as tmp:
            returncode, _ = build._run_latex([sys.executable, "-c", FAKE_LATEX, "30"], Path(tmp), 1)

        self.assertIsNone(returncode)


class PageProgressTestCase(SimpleTestCase):
    def test_copy_and_percent_reported_at_most_every_interval(self):
        reports = []
        on_page = build._page_progress(lambda percent, message: reports.append((percent, message)), 10, 50,
                                       "Compiling", copies=4, pages_per_copy=2, min_interval=3600)

        on_page(5)
        on_page(8)

        self.assertEqual(reports, [(10 + int(39 * 5 / 8), "Compiling: copy 3 / 4")])

    def test_estimate_too_small_stays_below_the_end(self):
        reports = []
        on_page = build._page_progress(lambda percent, message: reports.append((percent, message)), 10, 50,
                                       "Compiling", copies=2, pages_per_copy=1, min_interval=0)

        on_page(10)

        self.assertEqual(reports, [(49, "Compiling: copy 2 / 2")])

    def test_timeout_grows_with_the_pages(self):
        self.assertEqual(build._compile_timeout(60, 0), 120)
        self.assertEqual(build._compile_timeout(60, 4400), 120 + 4400)


class QrCacheTestCase(SimpleTestCase):
    AUX = (
        "\\relax\n"
        "\\ifx\\qr@savematrix\\@undefined\\def\\qr@savematrix{...}\\fi\n"
        "\\qr@savematrix{CePROExamsQRC,1,1}{2}{3}{1110}\n"
        "\\newlabel{lastpage}{{2}{2}}\n"
        "\\qr@savematrix{CePROExamsQRC,1,2}{2}{3}{0111}\n"
    )

    def test_only_the_qr_codes_are_kept(self):
        with tempfile.TemporaryDirectory() as tmp:
            aux = Path(tmp) / "amc-compiled.aux"
            aux.write_text(self.AUX, encoding="latin-1")

            cache = build.read_qr_cache(aux)
            self.assertEqual(len(cache), 3)
            self.assertFalse(any("newlabel" in line for line in cache))

            aux.unlink()
            build.seed_qr_cache(Path(tmp), cache)
            self.assertEqual(aux.read_text(encoding="latin-1"), "\\relax\n" + "\n".join(cache) + "\n")

    def test_no_previous_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(build.read_qr_cache(Path(tmp) / "amc-compiled.aux"), [])
            build.seed_qr_cache(Path(tmp), [])
            self.assertFalse((Path(tmp) / "amc-compiled.aux").exists())


class FakeAsyncResult:
    state = "PROGRESS"

    def __init__(self, task_id):
        self.task_id = task_id


@patch("celery.result.AsyncResult", FakeAsyncResult)
class ActiveFinalBuildJobTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()
        self.user = create_mock_user()
        self.user.is_superuser = True
        self.user.save()
        PrepStudent.objects.create(exam=self.exam, copy_no=1, sciper=123456, first_name="A", last_name="B", seat="1")
        self.job = ExamAMCJob.objects.create(exam=self.exam, requested_by=self.user, job_type="final_build",
                                             status="running", celery_task_id="task-1")

    def test_running_job(self):
        self.assertEqual(get_active_final_build_job(self.exam), self.job)
        self.assertIsNone(get_active_final_build_job(create_mock_exam(code="OTHER")))

    def test_old_or_failed_job_is_marked_interrupted(self):
        ExamAMCJob.objects.filter(pk=self.job.pk).update(created_at=timezone.now() - timedelta(hours=5))
        self.assertIsNone(get_active_final_build_job(self.exam))
        self.job.refresh_from_db()
        self.assertEqual(self.job.status, "error")

    def test_failed_task(self):
        with patch.object(FakeAsyncResult, "state", "FAILURE"):
            self.assertIsNone(get_active_final_build_job(self.exam))

    def test_second_start_follows_the_running_one(self):
        self.client.force_login(self.user)

        with patch("examc_app.views.preparation_views.generate_final_exam_files_task.apply_async") as start:
            response = self.client.get(reverse("generate_final_exam_files_start", kwargs={"exam_pk": self.exam.pk}))

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["task_id"], "task-1")
        start.assert_not_called()

    def test_page_shows_the_running_job(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("exam_preparation", kwargs={"exam_pk": self.exam.pk}))

        self.assertContains(response, 'activeFinalTaskId: "task-1"')
        self.assertContains(response, 'id="generate-final-button" disabled')
