

from django.urls import reverse

from examc_app.forms import UploadScansForm, ManageExamPagesGroupsForm, ManageExamReviewersForm, ExportMarkedFilesForm
import logging
from django.test import TestCase, Client, RequestFactory
from django_tequila.django_backend import User

from examc_app.models import Exam
from examc_app.views import ExamSelectView


class ViewsTestCase(TestCase):
    def __init__(self, methodName: str = "runTest"):
        super().__init__(methodName)
        self.factory = None

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', email='testuser@test.ch', password='testpassword')
        self.exam = Exam.objects.create(name='Test Exam')

    def test_exam_select_view(self):
        # request = RequestFactory().get("/")
        # view = ExamSelectView()
        # view.setup(request)
        # context = view.get_context_data()
        # self.assertIn('',context)

        self.client.login(username='testuser', email='testuser@test.ch', password='testpassword')
        data = {'name': 'test name', 'exam': self.exam}
        response = self.client.get(reverse('examSelect'))

        self.assertEqual(response.status_code, 302)
        #self.assertTemplateUsed(response, 'exam/exam_select.html')


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
        form_data = {'group_name': 'NomDuGroupe', 'page_from': 1, 'page_to': 5}
        form = ManageExamPagesGroupsForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_manage_exam_pages_groups_form_invalid_data(self):
        form = ManageExamPagesGroupsForm(data={})
        self.assertFalse(form.is_valid())
        logging.error(form.errors)
        invalid_data = {'group_name': 'NomDuGroupe', 'page_from': 5, 'page_to': 1}
        form = ManageExamPagesGroupsForm(data=invalid_data)
        print(form.errors)
        self.assertFalse(form.is_valid())




    def test_manage_exam_reviewers_form_valid_data(self):
        form_data = {'user': 'user', 'pages_groups': 'Group1, Group2'}
        form = ManageExamReviewersForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_manage_exam_reviewers_form_invalid_data(self):
        form = ManageExamReviewersForm(data={})
        self.assertFalse(form.is_valid())

        invalid_data = {'user': 'nonuser', 'pages_groups': 'Group1, Group2'}
        form = ManageExamReviewersForm(data=invalid_data)
        self.assertFalse(form.is_valid())

    def test_export_marked_files_form_valid_data(self):
        form_data = {'export_type': 1}
        form = ExportMarkedFilesForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_export_marked_files_form_invalid_data(self):
        form = ExportMarkedFilesForm(data={})
        self.assertFalse(form.is_valid())

        invalid_data = {'export_type': 5}
        form = ExportMarkedFilesForm(data=invalid_data)
        self.assertFalse(form.is_valid())


