from django.test import TestCase

from examc_app.forms import *
from examc_app.models import *


class FormsTestCase(TestCase):
    def test_upload_scans_form(self):
        form = UploadScansForm()
        self.assertTrue(form.fields['files'].widget.attrs.get('allow_multiple_selected'))

    def test_manage_exam_pages_groups_form(self):
        questions_choices = [
            ("Group 1", "Group 1"),
            ("Group 2", "Group 2"),
        ]

        form = ManagePagesGroupsForm(
            data={},
            questions_choices=questions_choices,
        )

        self.assertEqual(form.Meta.model, PagesGroup)
        self.assertEqual(
            form.Meta.fields,
            ["group_name", "nb_pages", "use_grading_scheme"],
        )

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

        self.assertEqual(
            form.fields["nb_pages"].widget.attrs.get("style"),
            "width:100px",
        )

        self.assertEqual(
            form.fields["nb_pages"].min_value,
            1,
        )

    def test_manage_exam_reviewers_form(self):
        form = ManageReviewersForm()

        self.assertEqual(form.Meta.model, ExamUser)
        self.assertEqual(form.Meta.fields, ['user', 'pages_groups'])

    def test_export_marked_files_form(self):
        form = ExportMarkedFilesForm()

        self.assertEqual(
            form.fields["export_type"].widget.__class__.__name__,
            "RadioSelect",
        )
        self.assertEqual(
            set(form.fields["export_type"].choices),
            {
                (1, "JPGs (one per page)"),
                (2, "PDFs (one per student copy)"),
            },
        )

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

