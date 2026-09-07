from django.contrib.auth.models import User, Permission, Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse
from django.utils.datastructures import MultiValueDict

from examc_app.forms import (
    UploadScansForm,
    ManagePagesGroupsForm,
    ManageReviewersForm,
    ExportMarkedFilesForm,
)
from examc_app.models import (
    ExamUser,
    PagesGroup,
    ReviewLock,
)
from examc_app.tests.helpers.models import (
    create_mock_semester,
    create_mock_academic_year,
    create_mock_user,
    create_mock_exam,
)


class ViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.semester = create_mock_semester()
        self.academic_year = create_mock_academic_year()
        self.user = create_mock_user()
        self.exam = create_mock_exam(
            semester=self.semester,
            year=self.academic_year,
        )

    def test_exam_select_view(self):
        self.client.login(
            username="testuser",
            password="testpassword",
        )

        response = self.client.get(reverse("examSelect"))

        self.assertEqual(response.status_code, 200)


class TestForms(TestCase):
    def setUp(self):
        self.semester = create_mock_semester()
        self.academic_year = create_mock_academic_year()
        self.exam = create_mock_exam(
            semester=self.semester,
            year=self.academic_year,
        )

    def test_upload_scans_form_valid_data(self):
        uploaded_file = SimpleUploadedFile(
            "scan.jpg",
            b"fake image content",
            content_type="image/jpeg",
        )

        form = UploadScansForm(
            files=MultiValueDict({"files": [uploaded_file]})
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["files"], uploaded_file)

    def test_upload_scans_form_invalid_data(self):
        form = UploadScansForm(
            files=MultiValueDict()
        )

        self.assertFalse(form.is_valid())
        self.assertIn("files", form.errors)

    def test_manage_exam_pages_groups_form_valid_data(self):
        questions_choices = [
            ("Group 1", "Group 1"),
            ("Group 2", "Group 2"),
        ]

        form_data = {
            "group_name": "Group 1",
            "nb_pages": 5,
            "use_grading_scheme": False,
        }

        form = ManagePagesGroupsForm(
            questions_choices,
            data=form_data,
        )

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["group_name"], "Group 1")
        self.assertEqual(form.cleaned_data["nb_pages"], 5)
        self.assertFalse(form.cleaned_data["use_grading_scheme"])

    def test_manage_exam_pages_groups_form_invalid_data(self):
        questions_choices = [
            ("Group 1", "Group 1"),
            ("Group 2", "Group 2"),
        ]

        # Missing required fields
        form = ManagePagesGroupsForm(
            questions_choices,
            data={},
        )

        self.assertFalse(form.is_valid())

        # Invalid choice
        form = ManagePagesGroupsForm(
            questions_choices,
            data={
                "group_name": "Invalid Group",
                "nb_pages": 5,
                "use_grading_scheme": False,
            },
        )

        self.assertFalse(form.is_valid())

        # nb_pages must be >= 1
        form = ManagePagesGroupsForm(
            questions_choices,
            data={
                "group_name": "Group 1",
                "nb_pages": 0,
                "use_grading_scheme": False,
            },
        )

        self.assertFalse(form.is_valid())

    def test_manage_exam_reviewers_form_valid_data(self):
        user = create_mock_user()

        pages_group = PagesGroup.objects.create(
            exam=self.exam,
            group_name="Group 1",
            nb_pages=5,
        )

        exam_user = ExamUser.objects.create(
            user=user,
            exam=self.exam,
        )
        exam_user.pages_groups.add(pages_group)

        form = ManageReviewersForm(instance=exam_user)

        self.assertTrue(form.is_bound is False)
        self.assertEqual(
            list(form.fields["pages_groups"].queryset),
            [pages_group],
        )
        self.assertTrue(form.fields["user"].disabled)
        self.assertEqual(
            form.fields["review_blocked"].widget.__class__.__name__,
            "SwitchWidget",
        )

    def test_manage_exam_pages_groups_form_fields(self):
        questions_choices = [
            ("Group 1", "Group 1"),
            ("Group 2", "Group 2"),
        ]

        form = ManagePagesGroupsForm(questions_choices)

        self.assertEqual(
            form.fields["group_name"].widget.__class__.__name__,
            "Select",
        )
        self.assertEqual(
            form.fields["nb_pages"].widget.__class__.__name__,
            "NumberInput",
        )
        self.assertEqual(
            form.fields["use_grading_scheme"].widget.__class__.__name__,
            "SwitchWidget",
        )

        self.assertEqual(form.fields["nb_pages"].min_value, 1)
        self.assertTrue(form.fields["group_name"].required)
        self.assertTrue(form.fields["nb_pages"].required)
        self.assertFalse(form.fields["use_grading_scheme"].required)

    def test_manage_exam_reviewers_form_invalid_data(self):
        user = create_mock_user()

        other_exam = create_mock_exam(
            semester=self.semester,
            year=self.academic_year,
            name="Other Exam",
            code="OTHER-EXAM",
        )

        other_pages_group = PagesGroup.objects.create(
            exam=other_exam,
            group_name="Other Group",
            nb_pages=5,
        )

        exam_user = ExamUser.objects.create(
            user=user,
            exam=self.exam,
        )

        form = ManageReviewersForm(
            data={
                "user": user.pk,
                "pages_groups": [other_pages_group.pk],
                "review_blocked": False,
            },
            instance=exam_user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("pages_groups", form.errors)

    def test_export_marked_files_form_valid_data(self):
        form = ExportMarkedFilesForm(
            data={
                "export_type": 1,
                "with_comments": 1,
            }
        )

        self.assertTrue(form.is_valid())

    def test_export_marked_files_form_invalid_data(self):
        form = ExportMarkedFilesForm(
            data={
                "export_type": 5,
                "with_comments": 1,
            }
        )

        self.assertFalse(form.is_valid())

    def test_export_marked_files_form_fields(self):
        form = ExportMarkedFilesForm()

        self.assertEqual(
            set(form.fields["export_type"].choices),
            {
                (1, "JPGs (one per page)"),
                (2, "PDFs (one per student copy)"),
            },
        )

        self.assertEqual(
            set(form.fields["with_comments"].choices),
            {
                (1, "Yes"),
                (2, "No"),
            },
        )

        self.assertEqual(form.fields["export_type"].initial, 2)
        self.assertEqual(form.fields["with_comments"].initial, 1)

class TestReviewView(TestCase):
    def setUp(self):
        self.user = create_mock_user()

        self.semester = create_mock_semester()
        self.academic_year = create_mock_academic_year()

        self.exam = create_mock_exam(
            semester=self.semester,
            year=self.academic_year,
        )

        review_group = Group.objects.create(name="Reviewer")

        ExamUser.objects.create(
            user=self.user,
            exam=self.exam,
            group=review_group,
        )

    def test_review_view(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "reviewView",
                kwargs={"exam_pk": self.exam.pk},
            )
        )

        self.assertEqual(response.status_code, 200)


from django.contrib.auth.models import Group, User


class TestReviewGroupView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@test.ch",
            password="testpassword",
        )

        self.semester = create_mock_semester()
        self.academic_year = create_mock_academic_year()

        self.exam = create_mock_exam(
            semester=self.semester,
            year=self.academic_year,
        )

        self.pages_group = PagesGroup.objects.create(
            exam=self.exam,
            group_name="Test Group",
            nb_pages=5,
        )

        review_group = Group.objects.create(name="Reviewer")

        ExamUser.objects.create(
            user=self.user,
            exam=self.exam,
            group=review_group,
        )

    def test_review_group_view(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "reviewGroup",
                kwargs={
                    "exam_pk": self.exam.pk,
                    "group_pk": self.pages_group.pk,
                    "currpage": 1,
                    "current_grading_scheme": 0,
                },
            )
        )

        self.assertEqual(response.status_code, 200)

class TestReviewLockView(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="testadmin",
            email="testadmin@test.ch",
            password="testpassword",
        )

        self.semester = create_mock_semester()
        self.academic_year = create_mock_academic_year()

        self.exam = create_mock_exam(
            semester=self.semester,
            year=self.academic_year,
        )

        self.pages_group = PagesGroup.objects.create(
            group_name="Test Group",
            exam=self.exam,
            nb_pages=5,
        )

    def test_lock_can_be_created_without_student_record(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "review_student_pages_group_is_locked",
                kwargs={"exam_pk": self.exam.pk},
            ),
            {
                "pages_group_id": self.pages_group.pk,
                "copy_no": "0001",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

        lock = ReviewLock.objects.get(
            pages_group=self.pages_group
        )

        self.assertEqual(lock.copy_no, "1")
        self.assertIsNone(lock.student)


class TestReviewSettingsView(TestCase):
    def setUp(self):
        self.user = create_mock_user()
        self.semester = create_mock_semester()
        self.academic_year = create_mock_academic_year()

        self.exam = create_mock_exam(
            semester=self.semester,
            year=self.academic_year,
        )

    def test_review_settings_view(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "reviewSettingsView",
                kwargs={
                    "exam_pk": self.exam.pk,
                    "curr_tab": "groups",
                },
            )
        )

        self.assertEqual(response.status_code, 403)