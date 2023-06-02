import logging

from django import forms
from django.forms import modelformset_factory
from .models import ExamPagesGroup

class UploadScansForm(forms.Form):
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))

class ManageExamPagesGroupsForm(forms.ModelForm):
    class Meta:
        model = ExamPagesGroup
        fields = ['group_name','page_from','page_to']

ExamPagesGroupsFormSet = modelformset_factory(
    ExamPagesGroup, fields=('id','group_name','page_from','page_to'), extra=0, can_delete=True
)

class ExportMarkedFilesForm(forms.Form):

    export_type = forms.ChoiceField(widget=forms.RadioSelect, choices=[(1,'JPGs (one per page)'),(2,'PDFs (one per student copy)')],
                  required=True)

    def __init__(self, *args, **kwargs):

        exam = kwargs.pop('exam', None)

        super(ExportMarkedFilesForm, self).__init__(*args, **kwargs)
