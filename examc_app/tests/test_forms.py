from django.test import TestCase
from examc_app.forms import UploadScansForm, ManageExamPagesGroupsForm, ManageExamReviewersForm, ExportMarkedFilesForm
from examc_app.models import *

class FormsTestCase(TestCase):
    def test_upload_scans_form(self):
        form = UploadScansForm()
        self.assertTrue(form.fields['files'].widget.attrs.get('allow_multiple_selected'))

    def test_manage_exam_pages_groups_form(self):
        form = ManageExamPagesGroupsForm()
        self.assertEqual(form.Meta.model, ExamPagesGroup)
        self.assertEqual(form.Meta.fields, ['group_name', 'page_from', 'page_to'])
        self.assertEqual(form.fields['group_name'].widget.attrs.get('style'), 'width:300px;')
        self.assertEqual(form.fields['page_from'].widget.attrs.get('style'), 'width:100px;')
        self.assertEqual(form.fields['page_to'].widget.attrs.get('style'), 'width:100px;')

    def test_manage_exam_reviewers_form(self):
        form = ManageExamReviewersForm()
        self.assertEqual(form.Meta.model, ExamReviewer)
        self.assertEqual(form.Meta.fields, ['user', 'pages_groups'])
        self.assertEqual(form.fields['user'].disabled, True)
        self.assertEqual(form.fields['user'].widget.attrs.get('style'), 'width:300px;')
        self.assertEqual(form.fields['pages_groups'].widget.attrs.get('style'), 'width:300px;')

    def test_export_marked_files_form(self):
        form = ExportMarkedFilesForm()
        self.assertEqual(form.fields['export_type'].widget.__class__.__name__, 'RadioSelect')
        self.assertEqual(form.fields['export_type'].choices, [(1, 'JPGs (one per page)'), (2, 'PDFs (one per student copy)')])

