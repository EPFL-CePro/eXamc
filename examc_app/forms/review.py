from django import forms
from django.forms import modelformset_factory
from django_summernote.widgets import SummernoteWidget

from examc_app.forms import SwitchWidget
from examc_app.models import PagesGroup, ExamUser, QuestionGradingSchemeCheckBox, QuestionGradingScheme


class UploadScansForm(forms.Form):
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))

class ManagePagesGroupsForm(forms.ModelForm):
    class Meta:
        model = PagesGroup
        fields = ['group_name', 'nb_pages', 'use_grading_scheme']

    def __init__(self, questions_choices, *args, **kwargs):
        super(ManagePagesGroupsForm, self).__init__(*args, **kwargs)
        self.fields['group_name'] = forms.ChoiceField(label='Question', choices=questions_choices, widget=forms.Select(
            attrs={'class': "selectpicker form-control", 'size': 5}), required=True)
        self.fields['nb_pages'] = forms.IntegerField(label='Nb pages',
                                      widget=forms.NumberInput(attrs={'class': "form-control", 'id': "nb_pages", 'style':'width:100px'}),
                                      required=True, min_value=1)
        self.fields['use_grading_scheme'] = forms.BooleanField(label='Use grading scheme', widget=SwitchWidget(),required=False)

PagesGroupsFormSet = modelformset_factory(
    PagesGroup, form=ManagePagesGroupsForm,  extra=0
)

class ManageReviewersForm(forms.ModelForm):
    # override the field to give it our SwitchWidget
    review_blocked = forms.BooleanField(
        required=False,
        widget=SwitchWidget(),
        label='Block review',
    )

    class Meta:
        model = ExamUser
        fields = ['user', 'pages_groups', 'review_blocked']

    def __init__(self, *args, **kwargs):
        super(ManageReviewersForm, self).__init__(*args, **kwargs)
        # filter many to many pagesgroup to get only for curr exam
        self.pages_groups_choices = PagesGroup.objects.filter(exam=kwargs.pop('instance').exam)
        self.fields['pages_groups'].queryset = self.pages_groups_choices
        self.fields['user'].widget.attrs['class'] = 'form-control'
        self.fields['user'].widget.attrs['style'] = 'width:300px'
        self.fields['user'].disabled = True
        self.fields['pages_groups'].widget.attrs['class'] = 'form-control'
        self.fields['pages_groups'].widget.attrs['style'] = 'width:300px'


ReviewersFormSet = modelformset_factory(ExamUser, form=ManageReviewersForm, extra=0)

class GradingSchemeForm(forms.ModelForm):
    class Meta:
        model = QuestionGradingScheme
        fields = ['name', 'max_points', 'description']

    def __init__(self, *args, **kwargs):
        super(GradingSchemeForm, self).__init__(*args, **kwargs)
        for fname, f in self.fields.items():
            f.widget.attrs['class'] = 'form-control'
            if fname == 'name':
                f.widget.attrs['style'] = 'min-width:300px'
            if fname == 'description':
                f.widget.attrs['rows'] = 1
                f.widget.attrs['style'] = 'min-width:400px'
            if fname == 'max_points':
                f.widget.attrs['style'] = 'min-width:150px'
                f.widget.attrs['readonly'] = True


GradingSchemeFormSet = modelformset_factory(QuestionGradingScheme, form=GradingSchemeForm, extra=0)

class GradingSchemeCheckBoxForm(forms.ModelForm):
    class Meta:
        model = QuestionGradingSchemeCheckBox
        fields = ['name', 'points', 'description', "position"]
        widgets = {
            "description": SummernoteWidget(
                attrs={"summernote": {"width": "100%", "height": "150px"}}
            ),
            "position": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super(GradingSchemeCheckBoxForm, self).__init__(*args, **kwargs)
        for fname, f in self.fields.items():
            if fname != 'description':
                f.widget.attrs['class'] = 'form-control'
                if fname == 'name':
                    f.widget.attrs['style'] = 'min-width:300px'
                if fname == 'points':
                    f.widget.attrs['style'] = 'min-width:150px'
            else:
                f.required = False


GradingSchemeCheckboxFormSet=modelformset_factory(QuestionGradingSchemeCheckBox, form=GradingSchemeCheckBoxForm, extra=0)