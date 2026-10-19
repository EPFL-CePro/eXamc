from datetime import date
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from examc_app.models import Exam, Question
from examc_app.services.exam.common import build_overall_exam_code
from examc_app.tests.helpers.models import (
    create_mock_academic_year,
    create_mock_exam,
    create_mock_semester,
    create_mock_user,
)


class CommonExamsTestCase(TestCase):
    def setUp(self):
        self.year = create_mock_academic_year(code="2024-2025")
        self.semester = create_mock_semester(code=2, name="Spring")

    def make_exam(self, code, *, overall=False, exam_date=date(2025, 6, 10), with_question=True):
        exam = create_mock_exam(code=code, name=code, semester=self.semester, year=self.year)
        exam.date = exam_date
        exam.overall = overall
        exam.save()
        if with_question:
            Question.objects.create(code="Q1", exam=exam, max_points=1)
        return exam

    def link(self, overall, *children):
        for child in children:
            child.common_exams.add(overall)


class BuildOverallExamCodeTests(CommonExamsTestCase):
    def test_removes_parenthesized_part_and_appends_month_year(self):
        exam = self.make_exam("MATH-106(A)")
        self.assertEqual(build_overall_exam_code(exam), "000_MATH-106_06-2025")

    def test_exams_differing_only_by_parentheses_share_the_same_code(self):
        exam_a = self.make_exam("MATH-106(A)")
        exam_b = self.make_exam("MATH-106(B)", exam_date=date(2025, 6, 12))
        self.assertEqual(build_overall_exam_code(exam_a), build_overall_exam_code(exam_b))

    def test_code_without_parentheses_is_kept(self):
        exam = self.make_exam("PHYS-101")
        self.assertEqual(build_overall_exam_code(exam), "000_PHYS-101_06-2025")


class GetOverallExamOrDefaultTests(CommonExamsTestCase):
    def test_returns_itself_when_not_linked_to_any_exam(self):
        exam = self.make_exam("MATH-106(A)")
        self.assertEqual(exam.get_overall_exam_or_default(), exam)

    def test_returns_itself_when_it_is_the_overall(self):
        child = self.make_exam("MATH-106(A)")
        overall = self.make_exam("000_MATH-106_06-2025", overall=True)
        self.link(overall, child)
        self.assertEqual(overall.get_overall_exam_or_default(), overall)

    def test_returns_the_overall_of_a_child_exam(self):
        child = self.make_exam("MATH-106(A)")
        overall = self.make_exam("000_MATH-106_06-2025", overall=True)
        self.link(overall, child)
        self.assertEqual(child.get_overall_exam_or_default(), overall)


class GetAvailableCommonExamsTests(CommonExamsTestCase):
    def test_overall_without_linked_exam_returns_empty_list(self):
        overall = self.make_exam("000_MATH-106_06-2025", overall=True, with_question=False)
        self.assertEqual(overall.get_available_common_exams(), [])

    def test_overall_lists_unlinked_siblings_but_not_linked_ones(self):
        linked = self.make_exam("MATH-106(A)")
        unlinked = self.make_exam("MATH-106(B)")
        overall = self.make_exam("000_MATH-106_06-2025", overall=True, with_question=False)
        self.link(overall, linked)

        available = overall.get_available_common_exams()

        self.assertIn(unlinked, available)
        self.assertNotIn(linked, available)
        self.assertNotIn(overall, available)

    def test_exams_of_another_semester_are_not_available(self):
        linked = self.make_exam("MATH-106(A)")
        other_semester = create_mock_semester(code=1, name="Autumn")
        other = create_mock_exam(code="MATH-106(B)", name="x", semester=other_semester, year=self.year)
        Question.objects.create(code="Q1", exam=other, max_points=1)
        overall = self.make_exam("000_MATH-106_06-2025", overall=True, with_question=False)
        self.link(overall, linked)

        self.assertNotIn(other, overall.get_available_common_exams())

    def test_regular_exam_lists_unlinked_siblings(self):
        exam = self.make_exam("MATH-106(A)")
        sibling = self.make_exam("MATH-106(B)")
        self.make_exam("PHYS-101")

        self.assertEqual(exam.get_available_common_exams(), [sibling])


class SetCommonExamViewTests(CommonExamsTestCase):
    def setUp(self):
        super().setUp()
        self.superuser = create_mock_user(username="admin", email="admin@test.ch")
        self.superuser.is_superuser = True
        self.superuser.save()
        self.client.force_login(self.superuser)

    @patch("examc_app.views.exam_views.generate_statistics")
    def test_creates_overall_with_generated_code_and_links_exam(self, mock_generate):
        mock_generate.delay.return_value = MagicMock(task_id="task-1")
        exam = self.make_exam("MATH-106(A)")

        response = self.client.post(reverse("set_common_exam", kwargs={"exam_pk": exam.pk}))

        overall = Exam.objects.get(code="000_MATH-106_06-2025")
        self.assertTrue(overall.overall)
        self.assertEqual(overall.name, "COMMON")
        self.assertIn(overall, exam.common_exams.all())
        self.assertEqual(
            response.url,
            reverse("examInfo", kwargs={"exam_pk": overall.pk, "task_id": "task-1"}),
        )

    @patch("examc_app.views.exam_views.generate_statistics")
    def test_second_exam_reuses_the_existing_overall(self, mock_generate):
        mock_generate.delay.return_value = MagicMock(task_id="task-1")
        exam_a = self.make_exam("MATH-106(A)")
        exam_b = self.make_exam("MATH-106(B)", exam_date=date(2025, 6, 12))

        self.client.post(reverse("set_common_exam", kwargs={"exam_pk": exam_a.pk}))
        self.client.post(reverse("set_common_exam", kwargs={"exam_pk": exam_b.pk}))

        self.assertEqual(Exam.objects.filter(overall=True).count(), 1)
        overall = Exam.objects.get(overall=True)
        self.assertEqual(exam_a.get_overall_exam_or_default(), overall)
        self.assertEqual(exam_b.get_overall_exam_or_default(), overall)
