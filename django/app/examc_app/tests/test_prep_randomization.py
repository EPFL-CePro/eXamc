import shutil
import tempfile
import unittest
from importlib import import_module
from pathlib import Path

from django.apps import apps
from django.contrib.auth.models import Group, User
from pypdf import PdfReader

from examc_app.forms.preparation import PrepQuestionAnswerForm, PrepQuestionForm
from examc_app.models import ExamUser, PrepQuestion, PrepQuestionAnswer, PrepStudent
from examc_app.services.preparation.questions_import import import_questions, parse_questions_tex
from examc_app.services.student.prep_amc_csv import write_students_csv
from examc_app.tests.helpers.prep import PrepViewsTestCase
from examc_app.utils.amc.amc_build_functions import compile_exam_in_workspace, copy_project_to_workspace
from examc_app.utils.preparation_functions import create_prep_question, create_prep_section
from examc_app.utils.preparation_latex_functions import update_exam_latex


class RandomizationDefaultsTestCase(PrepViewsTestCase):
    """The questions and the answers are shuffled unless the user switches it off."""

    def test_a_new_section_randomizes_its_questions(self):
        self.assertTrue(create_prep_section(self.exam).random_questions)

    def test_a_new_question_randomizes_its_answers(self):
        self.assertTrue(create_prep_question(self.section, self.types["SCQ"], nb_answers=3).random_answers)

    def test_an_imported_question_randomizes_its_answers(self):
        parsed = parse_questions_tex("\\begin{mcq}{Primes}\nWhich ones?\n\\begin{choices}\n"
                                     "\\correctchoice{2}\n\\wrongchoice{4}\n\\end{choices}\n\\end{mcq}\n")

        (question,) = import_questions(self.section, parsed)

        self.assertTrue(question.random_answers)

    def test_the_options_that_had_no_effect_are_gone(self):
        self.assertNotIn("canceled", PrepQuestionForm().fields)
        self.assertNotIn("new_page", PrepQuestionForm().fields)
        self.assertNotIn("fix_position", PrepQuestionAnswerForm().fields)

    def test_the_pages_do_not_offer_them_any_more(self):
        question = self.question("SCQ")
        answer = question.prepAnswers.first()

        question_page = self.client.get(self.url("prep_question_panel", question_id=question.pk))
        answer_page = self.client.get(self.url("prep_answer_panel", answer_id=answer.pk))

        self.assertContains(question_page, "Randomized answers")
        self.assertNotContains(question_page, "Cancel question")
        self.assertNotContains(question_page, "<label>Fixed</label>")
        self.assertNotContains(answer_page, "<label>Fixed</label>")


class RandomizationLatexTestCase(PrepViewsTestCase):
    def section_tex(self) -> str:
        update_exam_latex(self.exam)
        return (self.project_path() / "section_1.tex").read_text(encoding="utf-8")

    def test_section_shuffles_its_questions_or_keeps_their_order(self):
        self.question("SCQ")
        self.assertIn("\\setgroupmode{SECTION-1}{withoutreplacement}", self.section_tex())

        self.section.random_questions = False
        self.section.save()

        self.assertIn("\\setgroupmode{SECTION-1}{fixed}", self.section_tex())

    def test_answers_are_shuffled_unless_the_question_asks_to_keep_their_order(self):
        for code in ("SCQ", "MCQ"):
            with self.subTest(code=code):
                PrepQuestion.objects.all().delete()
                question = self.question(code)

                shuffled = self.section_tex()
                question.random_answers = False
                question.save()
                ordered = self.section_tex()

                self.assertIn("\\begin{ANSWER-choices}", shuffled)
                self.assertNotIn("ANSWER-choices[o]", shuffled)
                self.assertIn("\\begin{ANSWER-choices[o]}", ordered)

    def test_true_false_answers_always_keep_their_order(self):
        question = self.question("TF", answers=2)
        for random_answers in (True, False):
            question.random_answers = random_answers
            question.save()

            self.assertIn("\\begin{ANSWER-choiceshoriz[o]}", self.section_tex())


class ShuffleTheExistingAnswersTestCase(PrepViewsTestCase):
    def test_the_questions_that_exist_keep_their_shuffled_answers(self):
        migration = import_module("examc_app.migrations.0028_prep_randomization_and_unused_options")
        self.question("SCQ", 1)
        self.question("MCQ", 2)
        PrepQuestion.objects.update(random_answers=False)

        migration.shuffle_the_existing_answers(apps, None)

        self.assertEqual(list(PrepQuestion.objects.values_list("random_answers", flat=True)), [True, True])

    def test_the_sections_are_left_as_they_are(self):
        migration = import_module("examc_app.migrations.0028_prep_randomization_and_unused_options")
        self.section.random_questions = False
        self.section.save()

        migration.shuffle_the_existing_answers(apps, None)

        self.section.refresh_from_db()
        self.assertFalse(self.section.random_questions)


@unittest.skipUnless(shutil.which("pdflatex"), "pdflatex is needed to compile the copies")
class AnswersOrderOnTheCopiesTestCase(PrepViewsTestCase):
    """AMC really keeps the answers in order with [o], and shuffles them without it (checked on compiled copies)."""
    WORDS = ("alpha", "bravo", "charlie", "delta")
    COPIES = 6

    def setUp(self):
        super().setUp()
        # The first page prints the teachers of the exam
        teacher = User.objects.create(username="ada", first_name="Ada", last_name="Lovelace", email="ada@epfl.ch")
        ExamUser.objects.create(exam=self.exam, user=teacher, group=Group.objects.get_or_create(pk=2, defaults={"name": "teacher"})[0])

    def compile_orders(self, random_answers: bool) -> set[tuple[str, ...]]:
        PrepQuestion.objects.all().delete()
        question = self.question("MCQ", answers=0)
        question.random_answers = random_answers
        question.save()
        for position, word in enumerate(self.WORDS, start=1):
            PrepQuestionAnswer.objects.create(prep_question=question, title=f"A{position}", answer_text=word,
                                              is_correct=position == 1, position=position)
        for copy in range(1, self.COPIES + 1):
            PrepStudent.objects.get_or_create(exam=self.exam, copy_no=copy, defaults={
                "sciper": 100000 + copy, "first_name": "Ada", "last_name": f"Student{copy}", "seat": f"S{copy}"})

        update_exam_latex(self.exam, pages_per_copy=2)
        project = self.project_path()
        write_students_csv(self.exam, project)
        with tempfile.TemporaryDirectory() as workspace:
            copy_project_to_workspace(str(project), Path(workspace))
            result = compile_exam_in_workspace(Path(workspace), timeout=240, mode="subject")
            self.assertTrue(result["ok"], result.get("error", "")[-800:])
            pages = [page.extract_text() for page in PdfReader(Path(workspace) / "amc-compiled.pdf").pages]

        orders = set()
        for text in pages:
            positions = [(text.find(word), word) for word in self.WORDS]
            if all(position >= 0 for position, _ in positions):
                orders.add(tuple(word for _, word in sorted(positions)))
        return orders

    def test_answers_keep_their_order_when_they_are_not_randomized(self):
        self.assertEqual(self.compile_orders(random_answers=False), {self.WORDS})

    def test_answers_are_shuffled_when_they_are_randomized(self):
        self.assertGreater(len(self.compile_orders(random_answers=True)), 1)
