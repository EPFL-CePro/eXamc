from django.test import TestCase

from examc_app.models import (
    AcademicYear,
    ComVsIndStatistic,
    PagesGroup,
    PagesGroupComment,
    PageMarkers,
    Question,
    QuestionType,
    Scale,
    ScaleDistribution,
    Semester,
    Student,
    StudentQuestionAnswer,
    StudentScaleGrade, ScaleStatistic,
)
from examc_app.tests.helpers.models import (
    create_mock_exam,
    create_mock_semester,
    create_mock_user, create_mock_scale,
)


class ExamModelTestCase(TestCase):
    def setUp(self):
        self.user = create_mock_user()
        self.academic_year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.semester = Semester.objects.create(
            code=1,
            name="Autumn",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.academic_year,
        )

    def test_exam_str_method(self):
        self.assertEqual(
            str(self.exam),
            "EXAM1-Exam 1 2023-2024 1",
        )


class PagesGroupTestCase(TestCase):
    def setUp(self):
        self.semester = create_mock_semester(code=1)
        self.year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.year,
        )

    def test_pages_group_str_method(self):
        group = PagesGroup.objects.create(
            exam=self.exam,
            group_name="Group 1",
            nb_pages=5,
        )

        self.assertEqual(
            str(group),
            "Group 1 ( pages 5 )",
        )


class PagesGroupCommentTestCase(TestCase):
    def setUp(self):
        self.user = create_mock_user(
            username="test_user",
            first_name="Test",
            last_name="User",
        )
        self.semester = create_mock_semester(code=1)
        self.year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.year,
        )
        self.group = PagesGroup.objects.create(
            exam=self.exam,
            group_name="Group 1",
        )

    def test_pages_group_comment(self):
        comment = PagesGroupComment.objects.create(
            user=self.user,
            pages_group=self.group,
            content="Test Comment",
            is_new=True,
        )

        data = comment.serialize(curr_user_id=self.user.id)

        self.assertEqual(data["content"], "Test Comment")
        self.assertTrue(data["is_new"])


class PageMarkersTestCase(TestCase):
    def setUp(self):
        self.semester = create_mock_semester(code=1)
        self.year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.year,
        )
        self.group = PagesGroup.objects.create(
            exam=self.exam,
            group_name="Group 1",
            nb_pages=5,
        )

    def test_scan_markers_str_method(self):
        marker = PageMarkers.objects.create(
            copie_no="1",
            page_no="1",
            exam=self.exam,
            pages_group=self.group,
            filename="file1.pdf",
        )

        self.assertEqual(
            str(marker),
            "1 - file1.pdf EXAM1",
        )


class ScaleTestCase(TestCase):
    def setUp(self):
        self.semester = create_mock_semester(code=1)
        self.year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.year,
        )

        self.scale = Scale.objects.create(
            name="Test Scale",
            total_points=100,
            points_to_add=10,
            formula="Some Formula",
            final=True,
            exam=self.exam,
        )

    def test_scale_str_method(self):
        self.assertEqual(
            str(self.scale),
            "Test Scale(100, 10, Some Formula, True)"
            "EXAM1 - Exam 1 2023-2024 1",
        )


class QuestionTestCase(TestCase):
    def setUp(self):
        self.semester = create_mock_semester(code=1)
        self.year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.year,
        )
        self.question_type = QuestionType.objects.create(
            code="MCQ",
            name="Multiple Choice",
        )
        self.question = Question.objects.create(
            code="Q1",
            common=False,
            question_type=self.question_type,
            max_points=10.0,
            nb_answers=4,
            correct_answer="A",
            discriminatory_factor=1,
            upper_correct=5,
            lower_correct=2,
            di_calculation=0.5,
            tot_answers=10,
            remark="Some remarks",
            upper_avg=7.5,
            lower_avg=3.5,
            exam=self.exam,
        )

    def test_question_str_method(self):
        self.assertEqual(
            str(self.question),
            "Q1",
        )


class StudentTestCase(TestCase):
    def setUp(self):
        self.semester = create_mock_semester(code=1)
        self.year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.year,
        )

    def test_student_str_method(self):
        student = Student.objects.create(
            copie_no="1",
            sciper="123456",
            name="Test User",
            section="Section A",
            exam=self.exam,
        )

        self.assertEqual(
            str(student),
            "1 - 123456 Test User",
        )


class StudentQuestionAnswerTestCase(TestCase):
    def setUp(self):
        self.semester = create_mock_semester(code=1)
        self.year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.year,
        )
        self.student = Student.objects.create(
            copie_no="1",
            sciper="123456",
            name="John Doe",
            section="Section A",
            exam=self.exam,
        )
        self.question_type = QuestionType.objects.create(
            code="MCQ",
            name="Multiple Choice",
        )
        self.question = Question.objects.create(
            code="Q1",
            common=False,
            question_type=self.question_type,
            max_points=10.0,
            nb_answers=4,
            correct_answer="A",
            discriminatory_factor=1,
            upper_correct=5,
            lower_correct=2,
            di_calculation=0.5,
            tot_answers=10,
            remark="Some remarks",
            upper_avg=7.5,
            lower_avg=3.5,
            exam=self.exam,
        )

    def test_student_question_answer_creation(self):
        answer = StudentQuestionAnswer.objects.create(
            ticked="A",
            points=5.0,
            student=self.student,
            question=self.question,
        )

        self.assertEqual(answer.ticked, "A")
        self.assertEqual(answer.points, 5.0)
        self.assertEqual(answer.student, self.student)
        self.assertEqual(answer.question, self.question)


class StudentScaleGradeTestCase(TestCase):
    def setUp(self):
        self.semester = create_mock_semester(code=1)
        self.year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.year,
        )
        self.student = Student.objects.create(
            copie_no="1",
            sciper="123456",
            name="John Doe",
            section="Section A",
            exam=self.exam,
        )
        self.scale = Scale.objects.create(
            name="Test Scale",
            total_points=100,
            points_to_add=10,
            min_grade=1.0,
            max_grade=6.0,
            exam=self.exam,
        )

    def test_student_scale_grade_creation(self):
        scale_grade = StudentScaleGrade.objects.create(
            student=self.student,
            scale=self.scale,
            grade=4.5,
        )

        self.assertEqual(scale_grade.student, self.student)
        self.assertEqual(scale_grade.scale, self.scale)
        self.assertEqual(scale_grade.grade, 4.5)


class ScaleDistributionTestCase(TestCase):
    def setUp(self):
        self.exam = create_mock_exam()
        self.scale = create_mock_scale()
        self.scale_statistic = ScaleStatistic.objects.create(exam_id=self.exam.id, scale_id=self.scale.id)

    def test_scale_distribution_creation(self):
        scale_distribution = ScaleDistribution.objects.create(
            grade=4.0,
            quantity=10,
            scale_statistic_id=self.scale_statistic.id,
        )

        self.assertEqual(scale_distribution.grade, 4.0)
        self.assertEqual(scale_distribution.quantity, 10)


class ComVsIndStatisticTestCase(TestCase):
    def setUp(self):
        self.semester = create_mock_semester(code=1)
        self.year = AcademicYear.objects.create(
            code="2023-2024",
            name="2023 - 2024",
        )
        self.exam = create_mock_exam(
            code="EXAM1",
            name="Exam 1",
            semester=self.semester,
            year=self.year,
        )
        self.scale = Scale.objects.create(
            name="Test Scale",
            total_points=100,
            points_to_add=10,
            min_grade=1.0,
            max_grade=6.0,
            exam=self.exam,
        )

    def test_com_vs_ind_statistic_creation(self):
        statistic = ComVsIndStatistic.objects.create(
            exam=self.exam,
            section="Section A",
            scale=self.scale,
            glob_avg_grade=4.5,
            com_rate=60.0,
            com_avg_pts=75.0,
            com_avg_grade=4.0,
            ind_avg_pts=85.0,
            ind_avg_grade=4.7,
        )

        self.assertEqual(statistic.exam, self.exam)
        self.assertEqual(statistic.section, "Section A")
        self.assertEqual(statistic.scale, self.scale)
        self.assertEqual(statistic.glob_avg_grade, 4.5)
        self.assertEqual(statistic.com_rate, 60.0)
        self.assertEqual(statistic.com_avg_pts, 75.0)
        self.assertEqual(statistic.com_avg_grade, 4.0)
        self.assertEqual(statistic.ind_avg_pts, 85.0)
        self.assertEqual(statistic.ind_avg_grade, 4.7)