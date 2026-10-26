import tempfile
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from examc_app.models import Exam
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user


class PrintSettingsTestCase(TestCase):
    def setUp(self):
        projects_root = tempfile.TemporaryDirectory()
        self.addCleanup(projects_root.cleanup)
        override = override_settings(AMC_PROJECTS_ROOT=projects_root.name)
        self.projects_root = projects_root.name
        override.enable()
        self.addCleanup(override.disable)

        self.exam = create_mock_exam()
        user = create_mock_user()
        user.is_superuser = True
        user.save()
        self.client.force_login(user)
        self.url = reverse("prep_print_settings", kwargs={"exam_pk": self.exam.pk})

    def test_standard_by_default(self):
        self.assertEqual(self.exam.print_format, Exam.PRINT_FORMAT_STANDARD)

        response = self.client.get(self.url)

        self.assertContains(response, 'id="print-format-standard" value="standard"\n               checked')

    def test_booklet_is_saved_and_shown_on_the_button(self):
        response = self.client.post(self.url, {"print_format": "booklet"})

        self.exam.refresh_from_db()
        self.assertEqual(self.exam.print_format, Exam.PRINT_FORMAT_BOOKLET)
        self.assertContains(response, 'id="print-settings-badge" hx-swap-oob="true"')
        self.assertContains(response, "Booklet</span>")

    def test_the_format_is_written_for_the_latex_preview(self):
        self.client.post(self.url, {"print_format": "booklet"})
        generated_vars = next(Path(self.projects_root).rglob("examc_generated_vars.tex"))
        self.assertIn(r"\newcommand{\ExamcBooklet}{1}", generated_vars.read_text())

        self.client.post(self.url, {"print_format": "standard"})
        self.assertIn(r"\newcommand{\ExamcBooklet}{0}", generated_vars.read_text())

    def test_unknown_format_is_refused(self):
        response = self.client.post(self.url, {"print_format": "poster"})

        self.assertEqual(response.status_code, 400)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.print_format, Exam.PRINT_FORMAT_STANDARD)

    def test_finalized_exam_is_refused(self):
        self.exam.is_finalized = True
        self.exam.save()

        response = self.client.post(self.url, {"print_format": "booklet"})

        self.assertEqual(response.status_code, 403)
        self.exam.refresh_from_db()
        self.assertEqual(self.exam.print_format, Exam.PRINT_FORMAT_STANDARD)
