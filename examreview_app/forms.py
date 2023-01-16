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
