import logging

from django.test import TestCase, Client
from django.urls import reverse
from django_tequila.django_backend import User

from examc_app.forms import UploadScansForm, ManagePagesGroupsForm, ManageReviewersForm, ExportMarkedFilesForm
from examc_app.models import Exam, PagesGroup


class ViewsTestCase(TestCase):
    def __init__(self, methodName: str = "runTest"):
        super().__init__(methodName)
        self.factory = None

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='testuser@test.ch', password='testpassword')
        self.exam = Exam.objects.create(name='Test Exam')

    def test_exam_select_view(self):
        self.client.login(username='testuser', email='testuser@test.ch', password='testpassword')
        data = {'name': 'test name', 'exam': self.exam}
        response = self.client.get(reverse('examSelect'))

        self.assertEqual(response.status_code, 200)


class TestForms(TestCase):
    def setUp(self):
        self.exam = Exam.objects.create(name='Test Exam')

    def test_upload_scans_form_valid_data(self):
        form = UploadScansForm(data={'name': 'test name', 'exam': self.exam})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['exam_id'], Exam.objects)

    def test_upload_scans_form_invalid_data(self):
        form = UploadScansForm(data={})
        self.assertFalse(form.is_valid())

    def test_manage_exam_pages_groups_form_valid_data(self):
        form_data = {'group_name': 'GroupName', 'page_from': 1, 'page_to': 5}
        form = ManagePagesGroupsForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_manage_exam_pages_groups_form_invalid_data(self):
        form = ManagePagesGroupsForm(data={})
        self.assertFalse(form.is_valid())
        logging.error(form.errors)
        invalid_data = {'group_name': 'GroupName', 'page_from': 5, 'page_to': 1}
        form = ManagePagesGroupsForm(data=invalid_data)
        print(form.errors)
        self.assertFalse(form.is_valid())

    def test_manage_exam_reviewers_form_valid_data(self):
        form_data = {'user': 'user', 'pages_groups': 'Group1, Group2'}
        form = ManageReviewersForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_manage_exam_reviewers_form_invalid_data(self):
        form = ManageReviewersForm(data={})
        self.assertFalse(form.is_valid())

        invalid_data = {'user': 'nonuser', 'pages_groups': 'Group1, Group2'}
        form = ManageReviewersForm(data=invalid_data)
        self.assertFalse(form.is_valid())

    def test_export_marked_files_form_valid_data(self):
        form_data = {'export_type': 1}
        form = ExportMarkedFilesForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_export_marked_files_form_invalid_data(self):
        invalid_data = {'export_type': 5}
        form = ExportMarkedFilesForm(data=invalid_data)
        self.assertFalse(form.is_valid())


class TestReviewView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='testuser@test.ch', password='testpassword')
        self.exam = Exam.objects.create(name='Test Exam')

    def test_review_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reviewView', kwargs={'pk': self.exam.pk}))
        self.assertEqual(response.status_code, 200)


class TestReviewGroupView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='testuser@test.ch', password='testpassword')
        self.exam = Exam.objects.create(name='Test Exam')
        self.pages_group = PagesGroup.objects.create(group_name='Test Group', exam=self.exam)

    def test_review_group_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reviewGroup', kwargs={'pk': self.pages_group.pk, 'currpage': 1}))
        self.assertEqual(response.status_code, 200)


class TestReviewSettingsView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', email='testuser@test.ch', password='testpassword')
        self.exam = Exam.objects.create(name='Test Exam')

    def test_review_settings_view(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('reviewSettingsView', kwargs={'pk': self.exam.pk, 'curr_tab': 'groups'}))
        self.assertEqual(response.status_code, 403)
