from django.test import TestCase
from examc_app.models import Exam, ExamPagesGroup, ExamReviewer, ExamPagesGroupComment, ScanMarkers


class ExamModelTestCase(TestCase):
    def setUp(self):
        self.exam1 = Exam.objects.create(code="EXAM1", name="Exam 1", semester=1, year="2024")

    def test_exam_str_method(self):
        self.assertEqual(str(self.exam1), "EXAM1-Exam 1 2024 1")

    def test_get_max_points(self):
        group1 = ExamPagesGroup.objects.create(exam=self.exam1, group_name="Group 1", page_from=1, page_to=5)
        group2 = ExamPagesGroup.objects.create(exam=self.exam1, group_name="Group 2", page_from=6, page_to=10)

        self.assertEqual(self.exam1.get_max_points(), 0)

        ScanMarkers.objects.create(copie_no="1", page_no="1", exam=self.exam1, pages_group=group1, filename="file1.pdf")
        ScanMarkers.objects.create(copie_no="2", page_no="6", exam=self.exam1, pages_group=group2, filename="file2.pdf")

        self.assertEqual(self.exam1.get_max_points(), 2)
