import logging

from django import forms
from django.forms import modelformset_factory
from .models import ExamPagesGroup, ExamReviewer


class UploadScansForm(forms.Form):
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))

class ManageExamPagesGroupsForm(forms.ModelForm):
    class Meta:
        model = ExamPagesGroup
        fields = ['group_name','page_from','page_to']

    def __init__(self, *args, **kwargs):
        super(ManageExamPagesGroupsForm, self).__init__(*args, **kwargs)
        # you can iterate all fields here
        for fname, f in self.fields.items():
            f.widget.attrs['class'] = 'form-control'
            if fname == 'group_name':
                f.widget.attrs['style'] = 'width:300px;'
            else:
                f.widget.attrs['style'] = 'width:100px;'



ExamPagesGroupsFormSet = modelformset_factory(
    ExamPagesGroup, form=ManageExamPagesGroupsForm, can_delete=True, extra=0
)

class ManageExamReviewersForm(forms.ModelForm):

    class Meta:
        model = ExamReviewer
        fields = ['user','pages_groups']

    def __init__(self, *args, **kwargs):
        super(ManageExamReviewersForm, self).__init__(*args, **kwargs)
        # you can iterate all fields here
        for fname, f in self.fields.items():
            f.widget.attrs['style'] = 'width:300px;'
            f.widget.attrs['class'] = 'form-control'
            if fname == 'user':
                f.disabled = True

ExamReviewersFormSet = modelformset_factory(
    ExamReviewer, form=ManageExamReviewersForm, can_delete=True, extra=0
)

class ExportMarkedFilesForm(forms.Form):

    export_type = forms.ChoiceField(widget=forms.RadioSelect, choices=[(1,'JPGs (one per page)'),(2,'PDFs (one per student copy)')],
                  required=True)

    def __init__(self, *args, **kwargs):

        exam = kwargs.pop('exam', None)

        super(ExportMarkedFilesForm, self).__init__(*args, **kwargs)
