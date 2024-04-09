# (╯°□°）╯︵ ┻━┻
from django.test import TestCase
from examc_app.models import Exam, ExamPagesGroup, ExamReviewer, ExamPagesGroupComment, ScanMarkers, DrawnImage
from django.contrib.auth.models import User

class ExamModelTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test_user', first_name='Test', last_name='User')
        self.exam = Exam.objects.create(code="EXAM1", name="Exam 1", semester=1, year="2024")

    def test_exam_str_method(self):
        self.assertEqual(str(self.exam), "EXAM1-Exam 1 2024 1")

    # def test_get_max_points(self):
    #     group1 = ExamPagesGroup.objects.create(exam=self.exam, group_name="Group 1", page_from=1, page_to=5)
    #     group2 = ExamPagesGroup.objects.create(exam=self.exam, group_name="Group 2", page_from=6, page_to=10)
    #
    #     self.assertEqual(self.exam.get_max_points(), 0)
    #
    #     ScanMarkers.objects.create(copie_no="1", page_no="1", exam=self.exam, pages_group=group1, filename="file1.pdf")
    #     ScanMarkers.objects.create(copie_no="2", page_no="6", exam=self.exam, pages_group=group2, filename="file2.pdf")
    #
    #     self.assertEqual(self.exam.get_max_points(), 0)

class ExamPagesGroupTestCase(TestCase):
    def setUp(self):
        self.exam = Exam.objects.create(code="EXAM1", name="Exam 1", semester=1, year="2024")

    def test_exam_pages_group_str_method(self):
        group = ExamPagesGroup.objects.create(exam=self.exam, group_name="Group 1", page_from=1, page_to=5)
        self.assertEqual(str(group), "Group 1 ( pages 1...5 )")

class ExamReviewerTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test_user', first_name='Test', last_name='User')
        self.exam = Exam.objects.create(code="EXAM1", name="Exam 1", semester=1, year="2024")

    def test_exam_reviewer_str_method(self):
        reviewer = ExamReviewer.objects.create(exam=self.exam, user=self.user)
        self.assertEqual(str(reviewer), "EXAM1 - test_user")

class ExamPagesGroupCommentTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create(username='test_user', first_name='Test', last_name='User')
        self.exam = Exam.objects.create(code="EXAM1", name="Exam 1", semester=1, year="2024")
        self.group = ExamPagesGroup.objects.create(exam=self.exam, group_name="Group 1", page_from=1, page_to=5)

    def test_exam_pages_group_comment(self):
        comment = ExamPagesGroupComment.objects.create(user=self.user, pages_group=self.group, content="Test Comment", is_new=True)
        data = comment.serialize(curr_user_id=self.user.id)
        self.assertEqual(data['content'], "Test Comment")
        self.assertEqual(data['is_new'], True)

class ScanMarkersTestCase(TestCase):
    def setUp(self):
        self.exam = Exam.objects.create(code="EXAM1", name="Exam 1", semester=1, year="2024")
        self.group = ExamPagesGroup.objects.create(exam=self.exam, group_name="Group 1", page_from=1, page_to=5)

    def test_scan_markers_str_method(self):
        marker = ScanMarkers.objects.create(copie_no="1", page_no="1", exam=self.exam, pages_group=self.group, filename="file1.pdf")
        self.assertEqual(str(marker), "1 - file1.pdf EXAM1")

class DrawnImageTestCase(TestCase):
    def test_drawn_image_str_method(self):
        drawn_image = DrawnImage.objects.create(image_data=123, group_id=456)
        self.assertEqual(str(drawn_image), "Image (ID: 1)")
