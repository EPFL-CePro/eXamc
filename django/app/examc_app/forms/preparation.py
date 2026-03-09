# Preparation forms
from django import forms
from django.forms import modelformset_factory
from django_summernote.widgets import SummernoteWidget

from examc_app.models import PrepQuestionAnswer, QuestionType, PrepQuestion, PrepSection, Exam


class ExamFirstPageForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ["first_page_text"]
        widgets = {
            "first_page_text": SummernoteWidget(
                attrs={"summernote": {"width": "100%", "height": "300px"}}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_page_text"].required = False

class PrepSectionForm(forms.ModelForm):
    class Meta:
        model = PrepSection
        fields = ["title", "section_text", "position"]
        widgets = {
            "section_text": SummernoteWidget(
                attrs={"summernote": {"width": "100%", "height": "200px"}}
            ),
            "position": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].widget.attrs.update({
            "class": "form-control",
            "style": "min-width:300px",
        })


PrepSectionFormSet=modelformset_factory(PrepSection, form=PrepSectionForm, extra=0)

class PrepQuestionForm(forms.ModelForm):
    class Meta:
        model = PrepQuestion
        fields = ["title", "question_type", "question_text", "position"]
        widgets = {
            "question_text": SummernoteWidget(
                attrs={"summernote": {"width": "100%", "height": "250px"}}
            ),
            "position": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["title"].widget.attrs.update({
            "class": "form-control",
            "style": "min-width:300px",
        })

        self.fields["question_type"].widget.attrs.update({
            "class": "form-control",
            "style": "min-width:200px",
        })

PrepQuestionFormSet=modelformset_factory(PrepQuestion, form=PrepQuestionForm, extra=0)

class CreatePrepQuestionForm(forms.Form):
    section_pk = forms.IntegerField(widget=forms.HiddenInput())
    question_type = forms.ModelChoiceField(
        queryset=QuestionType.objects.all(),
        to_field_name="code",
        widget=forms.Select(attrs={"class": "form-control"})
    )
    title = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"})
    )
    nb_answers = forms.IntegerField(
        required=False,
        min_value=2,
        initial=4,
        widget=forms.NumberInput(attrs={"class": "form-control"})
    )

class PrepQuestionAnswerForm(forms.ModelForm):
    class Meta:
        model = PrepQuestionAnswer
        fields = ["title", "answer_text", "is_correct", "position"]
        widgets = {
            "answer_text": SummernoteWidget(
                attrs={"summernote": {"width": "100%", "height": "150px"}}
            ),
            "position": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["title"].widget.attrs.update({
            "class": "form-control",
            "style": "min-width:300px",
        })

        self.fields["is_correct"].widget.attrs.update({
            "class": "form-check-input",
        })

PrepQuestionAnswerFormSet = modelformset_factory(PrepQuestionAnswer, form=PrepQuestionAnswerForm, extra=0)