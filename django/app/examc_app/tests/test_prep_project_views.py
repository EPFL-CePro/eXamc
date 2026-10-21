from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.contrib.messages import get_messages
from django.urls import reverse

from examc_app.models import AcademicYear, Exam, ExamBuild, ExamUser
from examc_app.tests.helpers.models import create_mock_user
from examc_app.tests.helpers.prep import PrepViewsTestCase
from examc_app.utils.amc_functions import ensure_amc_project


class PreparationPageTestCase(PrepViewsTestCase):
    def test_page_shows_the_sections_and_gives_the_urls_to_the_script(self):
        response = self.client.get(self.url("exam_preparation"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="prep-root"')
        self.assertContains(response, "Algebra")
        self.assertContains(response, f'data-scoring-infos-url="{self.url("scoring_infos")}"')
        self.assertContains(response, f'data-preview-start-url="{self.url("exam_preview_start")}"')
        self.assertFalse(response.context["is_exam_locked"])

    def test_page_of_a_finalized_exam_is_locked(self):
        self.lock()

        response = self.client.get(self.url("exam_preparation"))

        self.assertTrue(response.context["is_exam_locked"])
        self.assertContains(response, 'data-is-locked="true"')

    def test_page_gives_the_links_of_the_final_files_of_a_finalized_exam(self):
        project = self.project_path()
        (project / f"{self.exam.code}-sujet.pdf").write_bytes(b"%PDF subject")
        (project / f"{self.exam.code}-catalog.pdf").write_bytes(b"%PDF catalog")
        build = ExamBuild.objects.create(exam=self.exam, version=1, status="ready", project_path=str(project))
        self.exam.is_finalized = True
        self.exam.finalized_build = build
        self.exam.save()

        context = self.client.get(self.url("exam_preparation")).context

        self.assertTrue(context["final_subject_pdf"])
        self.assertTrue(context["final_catalog_pdf"])

    def test_page_of_a_finalized_exam_without_its_files_has_no_links(self):
        build = ExamBuild.objects.create(exam=self.exam, version=1, status="ready", project_path=str(self.project_path()))
        self.exam.is_finalized = True
        self.exam.finalized_build = build
        self.exam.save()

        context = self.client.get(self.url("exam_preparation")).context

        self.assertEqual((context["final_subject_pdf"], context["final_catalog_pdf"]), ("", ""))

    def test_page_needs_the_manage_permission(self):
        self.client.force_login(create_mock_user(username="nobody", email="nobody@epfl.ch"))

        self.assertEqual(self.client.get(self.url("exam_preparation")).status_code, 403)

    def test_students_page_gives_the_url_of_the_table(self):
        response = self.client.get(self.url("preparation"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="prep-students-dt"')
        self.assertContains(response, f'data-api-url="{self.url("api-exam-prep-students-list")}"')
        self.assertContains(response, 'data-editable="true"')

    def test_students_page_of_a_locked_exam_is_not_editable(self):
        self.lock()

        response = self.client.get(self.url("exam_preparation_students"))

        self.assertContains(response, 'data-editable="false"')
        self.assertTrue(response.context["is_exam_locked"])


class UnlockEditingTestCase(PrepViewsTestCase):
    def test_unlock_makes_the_exam_editable_again_and_warns(self):
        self.exam.is_finalized = True
        self.exam.finalized_at = self.exam.date
        self.exam.save()

        response = self.client.post(self.url("unlock_exam_editing"))

        self.assertRedirects(response, self.url("exam_preparation"), fetch_redirect_response=False)
        self.exam.refresh_from_db()
        self.assertFalse(self.exam.is_finalized)
        self.assertIsNone(self.exam.finalized_at)
        self.assertIn("Editing has been unlocked", " ".join(str(m) for m in get_messages(response.wsgi_request)))

    def test_unlock_needs_a_post(self):
        self.lock()

        self.assertEqual(self.client.get(self.url("unlock_exam_editing")).status_code, 405)
        self.exam.refresh_from_db()
        self.assertTrue(self.exam.is_finalized)

    def test_unlock_needs_the_manage_permission(self):
        self.lock()
        self.client.force_login(create_mock_user(username="nobody", email="nobody@epfl.ch"))

        self.assertEqual(self.client.post(self.url("unlock_exam_editing")).status_code, 403)
        self.exam.refresh_from_db()
        self.assertTrue(self.exam.is_finalized)


class CreateExamProjectTestCase(PrepViewsTestCase):
    def __init__(self, methodName: str = "runTest"):
        super().__init__(methodName)

        self.COURSES = [
            {"coursCode": "MATH-101", "coursNomFr": "Analyse I"},
            {"coursCode": "PHYS-102", "coursNomFr": "Physique"}
        ]
        self.TEACHERS = {
            "MATH-101": [
                {"sciper": "123456", "name": "Ada Lovelace"}
            ]
        }

    def setUp(self):
        super().setUp()
        for name, value in (("get_courses", self.COURSES), ("get_teachers_names_by_course", self.TEACHERS)):
            patcher = patch(f"examc_app.views.preparation.project.{name}", return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def post(self, **fields):
        data = {"course": "MATH-101", "semester": self.exam.semester.pk, "date": "2026-06-20", **fields}
        return self.client.post("/create_exam_project", data)

    def test_form_lists_the_courses_with_their_teachers(self):
        response = self.client.get("/create_exam_project")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "MATH-101 - Analyse I (Ada Lovelace)")
        self.assertContains(response, "PHYS-102 - Physique")

    def test_creates_the_exam_its_teachers_and_the_project_files(self):
        teacher = User.objects.create(username="ada", first_name="Ada", last_name="Lovelace", email="ada@epfl.ch")
        Group.objects.get_or_create(pk=2, defaults={"name": "teacher"})

        with patch("examc_app.views.preparation.project.add_course_teachers_ldap", return_value=[teacher]) as ldap:
            response = self.post()

        exam = Exam.objects.get(code="MATH-101")
        self.assertRedirects(response, reverse("exam_info", kwargs={"exam_pk": exam.pk}), fetch_redirect_response=False)
        self.assertEqual((exam.name, exam.date, exam.semester, exam.year),
                         ("Analyse I", date(2026, 6, 20), self.exam.semester, self.exam.year))
        ldap.assert_called_once_with(["123456"])
        self.assertEqual(list(ExamUser.objects.filter(exam=exam).values_list("user__username", "group_id")),
                         [("ada", 2)])
        self.assertTrue((Path(ensure_amc_project(exam)) / "exam.tex").exists())

    def test_an_exam_of_the_same_course_and_date_is_refused(self):
        Exam.objects.create(code="MATH-101", name="Analyse I", semester=self.exam.semester, year=self.exam.year,
                            date=date(2026, 6, 20))

        with patch("examc_app.views.preparation.project.add_course_teachers_ldap", return_value=[]):
            response = self.post()

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An exam for this course and date already exists.")
        self.assertEqual(Exam.objects.filter(code="MATH-101").count(), 1)

    def test_a_course_that_is_not_offered_is_refused(self):
        with patch("examc_app.views.preparation.project.add_course_teachers_ldap", return_value=[]):
            response = self.post(course="NOPE-000")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Exam.objects.filter(code="NOPE-000").exists())

    def test_without_courses_the_form_says_so(self):
        with patch("examc_app.views.preparation.project.get_courses", return_value=[]):
            response = self.client.get("/create_exam_project")

        self.assertContains(response, "No courses are available")

    def test_without_academic_year_the_user_is_told_so(self):
        # An academic year cannot be deleted while an exam uses it
        Exam.objects.all().delete()
        AcademicYear.objects.all().delete()

        page = self.client.get("/create_exam_project")
        data = self.client.get("/create_exam_project", HTTP_ACCEPT="application/json")

        self.assertEqual(page.status_code, 400)
        self.assertContains(page, "No academic year", status_code=400)
        self.assertEqual(data.status_code, 400)
        self.assertEqual(data.json()["title"], "No academic year")
