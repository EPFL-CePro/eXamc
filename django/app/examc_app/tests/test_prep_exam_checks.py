from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from examc_app.models import PrepQuestion, PrepQuestionAnswer, PrepSection, PrepStudent, QuestionType
from examc_app.services.preparation.exam_checks import check_exam_content
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user


class ExamContentMixin:
    """An exam with a section "Algebra", and `question` to add questions to it."""

    def setUp(self):
        self.exam = create_mock_exam()
        self.types = {code: QuestionType.objects.create(code=code, name=code) for code in ("SCQ", "MCQ", "TF", "OPEN")}
        self.section = PrepSection.objects.create(exam=self.exam, title="Algebra", position=1)

    def question(self, code, correct=(), answers=2, text="Question?", section=None):
        """A question of type `code` with `answers` answers, the ones at the positions `correct` being correct."""
        section = section or self.section
        question = PrepQuestion.objects.create(prep_section=section, question_type=self.types.get(code),
                                               title=f"Q{section.prepQuestions.count() + 1}", question_text=text,
                                               position=section.prepQuestions.count() + 1)
        for position in range(1, answers + 1):
            PrepQuestionAnswer.objects.create(prep_question=question, title=f"Answer {position}",
                                              answer_text=f"Text {position}", is_correct=position in correct,
                                              position=position)
        return question


class ExamChecksTestCase(ExamContentMixin, TestCase):
    def test_valid_exam(self):
        self.question("SCQ", correct=[2])
        self.question("MCQ", correct=[1, 3], answers=3)
        self.question("TF", correct=[1])
        open_question = self.question("OPEN", answers=0)
        PrepQuestionAnswer.objects.create(prep_question=open_question, title="Zone", box_type="blank",
                                          box_height_mm=40, position=1)

        checks = check_exam_content(self.exam)

        self.assertEqual((checks.errors, checks.warnings), ([], []))

    def test_no_questions(self):
        checks = check_exam_content(self.exam)

        self.assertEqual(checks.errors, ["The exam has no questions."])
        self.assertEqual(checks.warnings, ['Section "Algebra": no question.'])

    def test_single_answer_questions_need_exactly_one_correct_answer(self):
        self.question("SCQ", correct=[])
        self.question("SCQ", correct=[1, 2])
        self.question("TF", correct=[])

        self.assertEqual(check_exam_content(self.exam).errors, [
            'Section "Algebra", question 1 "Q1" (SCQ): no correct answer.',
            'Section "Algebra", question 2 "Q2" (SCQ): 2 correct answers, only one is allowed.',
            'Section "Algebra", question 3 "Q3" (TF): no correct answer.',
        ])

    def test_too_few_answers_and_no_type(self):
        self.question("SCQ", correct=[1], answers=1)
        self.question("MCQ", answers=0)
        self.question("TF", correct=[1], answers=1)
        self.question(None)

        self.assertEqual(check_exam_content(self.exam).errors, [
            'Section "Algebra", question 1 "Q1" (SCQ): at least 2 answers are needed.',
            'Section "Algebra", question 2 "Q2" (MCQ): at least 2 answers are needed.',
            'Section "Algebra", question 3 "Q3" (TF): a true/false question needs its 2 answers TRUE and FALSE.',
            'Section "Algebra", question 4 "Q4" (no type): no question type.',
        ])

    def test_warnings(self):
        self.question("MCQ", correct=[])
        scq = self.question("SCQ", correct=[1], answers=3, text="  ")
        scq.prepAnswers.filter(position__in=[2, 3]).update(answer_text="")
        self.question("OPEN", answers=0)
        PrepSection.objects.create(exam=self.exam, title="Empty", position=2)

        checks = check_exam_content(self.exam)

        self.assertEqual(checks.errors, [])
        self.assertEqual(checks.warnings, [
            'Section "Algebra", question 1 "Q1" (MCQ): no correct answer (the students must tick none).',
            'Section "Algebra", question 2 "Q2" (SCQ): no question text.',
            'Section "Algebra", question 2 "Q2" (SCQ): answer 2, 3 without text.',
            'Section "Algebra", question 3 "Q3" (OPEN): no answer zone (no space to write on the copy).',
            'Section "Empty": no question.',
        ])


@patch("examc_app.views.preparation_views.generate_final_exam_files_task.apply_async")
class FinalGenerationChecksTestCase(ExamContentMixin, TestCase):
    def setUp(self):
        super().setUp()
        user = create_mock_user()
        user.is_superuser = True
        user.save()
        self.client.force_login(user)
        PrepStudent.objects.create(exam=self.exam, copy_no=1, sciper=123456, first_name="Ada", last_name="Lovelace",
                                   seat="A1")
        self.url = reverse("generate_final_exam_files_start", kwargs={"exam_pk": self.exam.pk})

    def test_errors_block(self, start):
        self.question("SCQ", correct=[])
        self.question("MCQ", correct=[])

        response = self.client.get(self.url, {"confirm_warnings": 1})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errors"], ['Section "Algebra", question 1 "Q1" (SCQ): no correct answer.'])
        self.assertEqual(len(response.json()["warnings"]), 1)
        start.assert_not_called()

    def test_warnings_confirmed_before_starting(self, start):
        start.return_value.id = "task-1"
        self.question("MCQ", correct=[])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["warnings"]), 1)
        self.assertNotIn("job_id", response.json())
        start.assert_not_called()

        response = self.client.get(self.url, {"confirm_warnings": 1})

        self.assertEqual(response.json()["task_id"], "task-1")
        start.assert_called_once()
