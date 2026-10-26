from typing import ClassVar

from django import forms
from django.test import TestCase

from examc_app.forms.results_statistics import ExportMarkedFilesForm, ExportResultsForm
from examc_app.forms.review import (
    ManagePagesGroupsForm,
    ManageReviewersForm,
    UploadScansForm,
)
from examc_app.models import ExamUser, PagesGroup


class UploadScansFormTests(TestCase):
    def test_files_widget_allows_multiple_selection(self):
        widget = UploadScansForm().fields["files"].widget
        self.assertTrue(widget.attrs.get("allow_multiple_selected"))

class ManagePagesGroupsFormTests(TestCase):
    def setUp(self):
        self.questions_choices = [
            ("Group 1", "Group 1"),
            ("Group 2", "Group 2"),
        ]
        self.form = ManagePagesGroupsForm(data={}, questions_choices=self.questions_choices)

    def test_meta(self):
        self.assertEqual(self.form.Meta.model, PagesGroup)
        self.assertEqual(self.form.Meta.fields, ["group_name", "nb_pages", "use_grading_scheme"])

    def test_group_name_is_a_select_with_the_given_choices(self):
        field = self.form.fields["group_name"]
        self.assertIsInstance(field.widget, forms.Select)
        self.assertEqual(list(field.widget.choices), self.questions_choices)

    def test_nb_pages_is_a_number_input_with_min_value_1(self):
        field = self.form.fields["nb_pages"]
        self.assertIsInstance(field.widget, forms.NumberInput)
        self.assertEqual(field.widget.attrs.get("style"), "width:100px")
        self.assertEqual(field.min_value, 1)

    def test_use_grading_scheme_uses_switch_widget(self):
        widget = self.form.fields["use_grading_scheme"].widget
        self.assertEqual(type(widget).__name__, "SwitchWidget")


class ManageReviewersFormTests(TestCase):
    def test_meta(self):
        self.assertEqual(ManageReviewersForm.Meta.model, ExamUser)
        self.assertEqual(
            list(ManageReviewersForm.Meta.fields), ["pages_groups", "review_blocked"]
        )

class ExportMarkedFilesFormTests(TestCase):
    def test_export_type_field(self):
        field = ExportMarkedFilesForm().fields["export_type"]

        self.assertEqual(type(field.widget).__name__, "InlineRadioSelect")
        self.assertEqual(
            set(field.choices),
            {
                (1, "JPGs (one per page)"),
                (2, "PDFs (one per student copy)"),
            },
        )


class ExportResultsFormTests(TestCase):
    CHECKBOXES: ClassVar = {
        "exportIsaCsv": "Export ISA CSV file",
        "exportExamScalePdf": "Export Exam scale PDF file",
        "exportStudentsDataCsv": "Export Students data CSV file",
    }

    def setUp(self):
        self.form = ExportResultsForm()

    def test_checkbox_fields(self):
        for name, label in self.CHECKBOXES.items():
            with self.subTest(field=name):
                field = self.form.fields[name]
                self.assertIsInstance(field, forms.BooleanField)
                self.assertEqual(field.label, label)
                self.assertIsInstance(field.widget, forms.CheckboxInput)
                self.assertEqual(field.widget.attrs.get("class"), "form-check-input")

    def test_scale_field(self):
        field = self.form.fields["scale"]
        self.assertIsInstance(field, forms.ChoiceField)
        self.assertIsInstance(field.widget, forms.RadioSelect)
        self.assertEqual(field.widget.attrs.get("class"), "form-check-input")