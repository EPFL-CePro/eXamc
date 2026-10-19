from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from examc_app.models import ExamAMCJob, PrepQuestion, PrepQuestionAnswer, PrepSection, QuestionType
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user


class StateChangingViewsTestCase(TestCase):
    """The views that change the exam only accept POST: a GET is not protected by the CSRF token, a link or an image
    of another page could otherwise delete a section or start a generation."""

    def setUp(self):
        user = create_mock_user()
        user.is_superuser = True
        user.save()
        self.client.force_login(user)

        self.exam = create_mock_exam()
        self.section = PrepSection.objects.create(exam=self.exam, title="Algebra", position=1)
        question_type = QuestionType.objects.create(code="SCQ", name="SCQ")
        self.question = PrepQuestion.objects.create(prep_section=self.section, question_type=question_type,
                                                    title="Q1", question_text="Question?", position=1)
        self.answer = PrepQuestionAnswer.objects.create(prep_question=self.question, title="A1", answer_text="One",
                                                        is_correct=True, position=1)

    def url(self, name, **kwargs):
        return reverse(name, kwargs={"exam_pk": self.exam.pk, **kwargs})

    def test_get_changes_nothing(self):
        urls = [
            self.url("add_prep_section"),
            self.url("delete_prep_section", section_id=self.section.pk),
            self.url("delete_prep_question", question_id=self.question.pk),
            self.url("add_prep_answer", question_id=self.question.pk),
            self.url("delete_prep_answer", answer_id=self.answer.pk),
            self.url("save_latex_edited_file"),
            self.url("generate_final_exam_files_start"),
            self.url("exam_preview_start"),
        ]

        with patch("examc_app.views.preparation.final_generation.generate_final_exam_files_task.apply_async") as start, \
                patch("examc_app.views.preparation.preview.compile_exam_preview_task.apply_async") as preview:
            for url in urls:
                with self.subTest(url=url):
                    self.assertEqual(self.client.get(url).status_code, 405)

        start.assert_not_called()
        preview.assert_not_called()
        self.assertEqual(PrepSection.objects.filter(exam=self.exam).count(), 1)
        self.assertEqual(PrepQuestion.objects.filter(prep_section=self.section).count(), 1)
        self.assertEqual(PrepQuestionAnswer.objects.filter(prep_question=self.question).count(), 1)
        self.assertFalse(ExamAMCJob.objects.filter(exam=self.exam).exists())

    def test_post_still_works(self):
        with patch("examc_app.views.preparation.answers.update_exam_latex"):
            response = self.client.post(self.url("delete_prep_answer", answer_id=self.answer.pk))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(PrepQuestionAnswer.objects.filter(pk=self.answer.pk).exists())
