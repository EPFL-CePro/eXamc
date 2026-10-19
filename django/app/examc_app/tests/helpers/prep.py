import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from django.test import TestCase, override_settings
from django.urls import reverse

from examc_app.models import PrepQuestion, PrepQuestionAnswer, PrepSection, QuestionType
from examc_app.tests.helpers.models import create_mock_exam, create_mock_user
from examc_app.utils.amc_functions import ensure_amc_project


class PrepViewsTestCase(TestCase):
    """
    Base of the tests of the preparation views: a manager is logged in, the AMC projects are in a temporary folder
    (the views write the LaTeX files of the exam), and the exam has a date, a section and the question types.
    """

    def setUp(self):
        projects_root = tempfile.TemporaryDirectory()
        self.addCleanup(projects_root.cleanup)
        override = override_settings(AMC_PROJECTS_ROOT=projects_root.name)
        override.enable()
        self.addCleanup(override.disable)

        # The templates of the pages ask the Vite manifest of the frontend, which is not built where the tests run
        vite = patch("django_vite.templatetags.django_vite.DjangoViteAssetLoader", MagicMock())
        vite.start()
        self.addCleanup(vite.stop)

        self.user = create_mock_user()
        self.user.is_superuser = True
        self.user.save()
        self.client.force_login(self.user)

        self.exam = create_mock_exam()
        self.exam.date = date(2026, 1, 15)
        self.exam.save()
        self.types = {code: QuestionType.objects.get_or_create(code=code, defaults={"name": code})[0]
                      for code in ("SCQ", "MCQ", "TF", "OPEN")}
        self.section = PrepSection.objects.create(exam=self.exam, title="Algebra", position=1)

    def url(self, name, **kwargs):
        return reverse(name, kwargs={"exam_pk": self.exam.pk, **kwargs})

    def project_path(self) -> Path:
        return Path(ensure_amc_project(self.exam))

    def question(self, code="SCQ", position=1, section=None, answers=2) -> PrepQuestion:
        question = PrepQuestion.objects.create(prep_section=section or self.section, question_type=self.types[code],
                                               title=f"Q{position}", question_text="Question?", position=position)
        for answer_position in range(1, answers + 1):
            PrepQuestionAnswer.objects.create(prep_question=question, title=f"A{answer_position}",
                                              answer_text=f"Answer {answer_position}",
                                              is_correct=answer_position == 1, position=answer_position)
        return question

    def lock(self):
        """The exam cannot be modified: it is finalized."""
        self.exam.is_finalized = True
        self.exam.save(update_fields=["is_finalized"])

    def post_json(self, url, payload):
        return self.client.post(url, data=json.dumps(payload), content_type="application/json")

    @staticmethod
    def positions(queryset) -> list[tuple[str, int]]:
        return [(item.title, item.position) for item in queryset.order_by("position", "pk")]
