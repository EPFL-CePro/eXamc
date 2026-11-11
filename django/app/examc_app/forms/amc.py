from django import forms


class AnnotateForm(forms.Form):
    """
    Options of the corrected exams generation, as posted by the Reports tab's form.
    Checkbox-like fields: "true" / "false", or left out when off.
    """
    single_file = forms.BooleanField(required=False)
    add_grading_scheme_report = forms.BooleanField(required=False)
    include_grading_scheme_description = forms.BooleanField(required=False)
    include_student_comments = forms.BooleanField(required=False)