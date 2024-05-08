from django.test import TestCase
from examc_app.forms import *
from examc_app.models import *


class FormsTestCase(TestCase):
    def test_upload_scans_form(self):
        form = UploadScansForm()
        self.assertTrue(form.fields['files'].widget.attrs.get('allow_multiple_selected'))

    def test_manage_exam_pages_groups_form(self):
        form = ManagePagesGroupsForm()
        self.assertEqual(form.Meta.model, PagesGroup)
        self.assertEqual(form.Meta.fields, ['group_name', 'page_from', 'page_to'])
        self.assertEqual(form.fields['group_name'].widget.attrs.get('style'), 'width:300px;')
        self.assertEqual(form.fields['page_from'].widget.attrs.get('style'), 'width:100px;')
        self.assertEqual(form.fields['page_to'].widget.attrs.get('style'), 'width:100px;')

    def test_manage_exam_reviewers_form(self):
        form = ManageReviewersForm()
        self.assertEqual(form.Meta.model, Reviewer)
        self.assertEqual(form.Meta.fields, ['user', 'pages_groups'])
        self.assertEqual(form.fields['user'].disabled, True)
        self.assertEqual(form.fields['user'].widget.attrs.get('style'), 'width:300px;')
        self.assertEqual(form.fields['pages_groups'].widget.attrs.get('style'), 'width:300px;')

    def test_export_marked_files_form(self):
        form = ExportMarkedFilesForm()
        self.assertEqual(form.fields['export_type'].widget.__class__.__name__, 'RadioSelect')
        self.assertEqual(form.fields['export_type'].choices,
                         [(1, 'JPGs (one per page)'), (2, 'PDFs (one per student copy)')])

    def test_login_pages_form(self):
        form = LoginForm()
        self.assertIsInstance(form.fields['username'], forms.CharField)
        self.assertIsInstance(form.fields['password'], forms.CharField)
        self.assertEqual(form.fields['username'].max_length, 65)
        self.assertEqual(form.fields['password'].max_length, 65)
        self.assertIsInstance(form.fields['password'].widget, forms.PasswordInput)

    def test_export_results_form(self):
        form = ExportResultsForm()

        self.assertIn('exportIsaCsv', form.fields)
        self.assertIn('exportExamScalePdf', form.fields)
        self.assertIn('exportStudentsDataCsv', form.fields)
        self.assertIn('scale', form.fields)

        self.assertIsInstance(form.fields['exportIsaCsv'], forms.BooleanField)
        self.assertIsInstance(form.fields['exportExamScalePdf'], forms.BooleanField)
        self.assertIsInstance(form.fields['exportStudentsDataCsv'], forms.BooleanField)
        self.assertIsInstance(form.fields['scale'], forms.ChoiceField)

        self.assertEqual(form.fields['exportIsaCsv'].label, 'export ISA .csv')
        self.assertEqual(form.fields['exportExamScalePdf'].label, 'export Exam scale pdf')
        self.assertEqual(form.fields['exportStudentsDataCsv'].label, 'export Students data .csv')

        self.assertIsInstance(form.fields['exportIsaCsv'].widget, forms.CheckboxInput)
        self.assertIsInstance(form.fields['exportExamScalePdf'].widget, forms.CheckboxInput)
        self.assertIsInstance(form.fields['exportStudentsDataCsv'].widget, forms.CheckboxInput)
        self.assertIsInstance(form.fields['scale'].widget, forms.RadioSelect)

        self.assertEqual(form.fields['exportIsaCsv'].widget.attrs['class'], 'form-check-input')
        self.assertEqual(form.fields['exportExamScalePdf'].widget.attrs['class'], 'form-check-input')
        self.assertEqual(form.fields['exportStudentsDataCsv'].widget.attrs['class'], 'form-check-input')
        self.assertEqual(form.fields['scale'].widget.attrs['class'], 'custom-radio-list form-check-inline')

