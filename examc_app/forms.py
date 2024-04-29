import logging

from django import forms
from django.forms import modelformset_factory
from .models import PagesGroup, Reviewer


class UploadScansForm(forms.Form):
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))


class ManagePagesGroupsForm(forms.ModelForm):
    class Meta:
        model = PagesGroup
        fields = ['group_name', 'page_from', 'page_to']

    def __init__(self, *args, **kwargs):
        super(ManagePagesGroupsForm, self).__init__(*args, **kwargs)
        # you can iterate all fields here
        for fname, f in self.fields.items():
            f.widget.attrs['class'] = 'form-control'
            if fname == 'group_name':
                f.widget.attrs['style'] = 'width:300px;'
            else:
                f.widget.attrs['style'] = 'width:100px;'


PagesGroupsFormSet = modelformset_factory(
    PagesGroup, form=ManagePagesGroupsForm,  extra=0
)


class ManageReviewersForm(forms.ModelForm):
    class Meta:
        model = Reviewer
        fields = ['user', 'pages_groups']

    def __init__(self, *args, **kwargs):
        super(ManageReviewersForm, self).__init__(*args, **kwargs)
        # you can iterate all fields here
        for fname, f in self.fields.items():
            f.widget.attrs['style'] = 'width:300px;'
            f.widget.attrs['class'] = 'form-control'
            if fname == 'user':
                f.disabled = True


ReviewersFormSet = modelformset_factory(Reviewer, form=ManageReviewersForm, extra=0)


class ExportMarkedFilesForm(forms.Form):
    export_type = forms.ChoiceField(widget=forms.RadioSelect,
                                    choices=[(1, 'JPGs (one per page)'), (2, 'PDFs (one per student copy)')],
                                    required=True)

    def __init__(self, *args, **kwargs):
        exam = kwargs.pop('exam', None)

        super(ExportMarkedFilesForm, self).__init__(*args, **kwargs)


class LoginForm(forms.Form):
    username = forms.CharField(max_length=65)
    password = forms.CharField(max_length=65, widget=forms.PasswordInput)

class ExportResultsForm(forms.Form):

    exportIsaCsv = forms.BooleanField(label='export ISA .csv', label_suffix=' ',initial=False, required=False, widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))
    exportExamScalePdf = forms.BooleanField(label='export Exam scale pdf', label_suffix=' ',initial=False, required=False,widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))
    exportStudentsDataCsv = forms.BooleanField(label='export Students data .csv', label_suffix=' ',initial=False, required=False,widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))

    def __init__(self, *args, **kwargs):

        EXAM = kwargs.pop('exam', None)

        super(ExportResultsForm, self).__init__(*args, **kwargs)

        if EXAM and EXAM.scaleStatistics:

            if EXAM.overall:
                self.fields['common_exams'] = forms.MultipleChoiceField(
                        widget=forms.CheckboxSelectMultiple(attrs={'class': "custom-radio-list form-check-inline"}),
                        choices=[ (c.pk,c.code+" "+c.primary_user.last_name) for c in EXAM.common_exams.all()],required=False)

            self.fields['scale'].choices=[ (s.pk, s.name) for s in EXAM.scales.all()]


    scale = forms.ChoiceField(choices=(),widget=forms.RadioSelect(attrs={'class': "custom-radio-list form-check-inline"}),required=True)