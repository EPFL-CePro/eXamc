import shutil
import unittest

from django.contrib.auth.models import Group, User

from examc_app.models import ExamUser
from examc_app.tests.helpers.prep import PrepViewsTestCase
from examc_app.utils.preparation_functions import compile_exam_preview
from examc_app.utils.preparation_latex_functions import update_exam_latex


class FirstPageTeachersTestCase(PrepViewsTestCase):
    def add_user(self, username, first_name, last_name, group_pk=2):
        user = User.objects.create(username=username, first_name=first_name, last_name=last_name,
                                   email=f"{username}@epfl.ch")
        group = Group.objects.get_or_create(pk=group_pk, defaults={"name": f"group {group_pk}"})[0]
        ExamUser.objects.create(exam=self.exam, user=user, group=group)

    def first_page(self) -> str:
        update_exam_latex(self.exam)
        return (self.project_path() / "first_page.tex").read_text(encoding="utf-8")

    def test_teachers_are_given_by_their_initial_and_last_name(self):
        self.add_user("ada", "Ada", "Lovelace")
        self.add_user("grace", "Grace", "Hopper")

        self.assertIn("\\bf A. Lovelace, G. Hopper", self.first_page())

    def test_only_the_teachers_of_the_exam_are_listed(self):
        self.add_user("ada", "Ada", "Lovelace")
        self.add_user("reviewer", "Alan", "Turing", group_pk=3)

        first_page = self.first_page()

        self.assertIn("A. Lovelace", first_page)
        self.assertNotIn("Turing", first_page)

    def test_a_teacher_without_first_name_is_given_by_the_last_name(self):
        self.add_user("ada", "", "Lovelace")

        self.assertIn("\\bf Lovelace", self.first_page())

    def test_an_exam_without_teacher_keeps_an_empty_line_for_them(self):
        first_page = self.first_page()

        # The template goes on with \\ : LaTeX refuses it after nothing
        self.assertIn("\\bf \\mbox{}", first_page)


@unittest.skipUnless(shutil.which("pdflatex"), "pdflatex is needed to compile the exam")
class FirstPageCompilationTestCase(PrepViewsTestCase):
    def test_exam_without_teacher_compiles(self):
        self.question("SCQ")

        result = compile_exam_preview(self.exam, job_id=1)

        self.assertTrue(result["ok"], str(result.get("error", ""))[-600:])
