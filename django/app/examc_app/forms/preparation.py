# Preparation forms
from django import forms
from django.forms import modelformset_factory, BaseModelFormSet
from django.utils.safestring import mark_safe
from django_summernote.widgets import SummernoteWidget

from examc_app.models import PrepQuestionAnswer, QuestionType, PrepQuestion, PrepSection, Exam, PrepScoringFormula

class SwitchWidget(forms.CheckboxInput):
    def render(self, name, value, attrs=None, renderer=None):
        attrs = {**(attrs or {}), 'class': 'custom-control-input'}
        if 'id' not in attrs:
            attrs['id'] = f'id_{name}'
        checkbox_html = super().render(name, value, attrs)
        label_html = (
            f'<label class="custom-control-label" '
            f'for="{attrs["id"]}"></label>'
        )
        return mark_safe(
            f'<div class="custom-control custom-switch" style="width:150px;text-align:center;">'
            f'{checkbox_html}'
            f'{label_html}'
            f'</div>'
        )

class ExamFirstPageForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ["first_page_text"]
        widgets = {
            "first_page_text": SummernoteWidget(
                attrs={"summernote": {"width": "100%"}}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["first_page_text"].required = False

class PrepSectionForm(forms.ModelForm):
    class Meta:
        model = PrepSection
        fields = ["title", "section_text", "position","random_questions"]
        widgets = {
            "section_text": SummernoteWidget(
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
        self.fields["random_questions"] = forms.BooleanField(label='Randomized questions', widget=SwitchWidget(),required=False)

class PrepQuestionForm(forms.ModelForm):
    class Meta:
        model = PrepQuestion
        fields = ["title", "question_type", "question_text", "position","max_points","random_answers","point_increment","canceled"]
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
            "style": "width:250px",
        })
        self.fields["max_points"] = forms.DecimalField(widget=forms.NumberInput(attrs={'class': "form-control",'style':'width:100px'}),
           decimal_places=1,required=False, min_value=0)
        self.fields["point_increment"].widget.attrs.update({
            "class": "form-control",
            "style": "width:100px",
        })
        self.fields["random_answers"] = forms.BooleanField(label='Randomized answers', widget=SwitchWidget(),required=False)
        self.fields["canceled"] = forms.BooleanField(label='Cancel question', widget=SwitchWidget(),
                                                           required=False)

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
        fields = ["title", "answer_text", "is_correct", "position", "box_type", "box_height_mm","fix_position"]
        widgets = {
            "answer_text": SummernoteWidget(
                attrs={"summernote": {"width": "100%", "height": "180px"}}
            ),
            "position": forms.HiddenInput(),
            "box_type": forms.Select(attrs={"class": "form-control", "min-width":"100px"}),
            "box_height_mm": forms.NumberInput(attrs={"class": "form-control"}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["title"].widget.attrs.update({
            "class": "form-control",
            "style": "min-width:300px",
        })
        self.fields["is_correct"] = forms.BooleanField(label='Correct', widget=SwitchWidget(), required=False)
        self.fields["fix_position"] = forms.BooleanField(label='Fixed', widget=SwitchWidget(), required=False)

PrepQuestionAnswerFormSet = modelformset_factory(PrepQuestionAnswer, form=PrepQuestionAnswerForm, extra=0)


def get_existing_question_type_ids(exam_pk, scope, prep_section=None, prep_question=None, prep_answer=None, exclude_pk=None):
    qs = PrepScoringFormula.objects.filter(exam_id=exam_pk)

    if scope == "exam":
        qs = qs.filter(
            prep_section__isnull=True,
            prep_question__isnull=True,
            prep_answer__isnull=True,
        )
    elif scope == "section":
        qs = qs.filter(
            prep_section_id=prep_section,
            prep_question__isnull=True,
            prep_answer__isnull=True,
        )
    elif scope == "question":
        qs = qs.filter(
            prep_question_id=prep_question,
            prep_answer__isnull=True,
        )
    elif scope == "answer":
        qs = qs.filter(
            prep_answer_id=prep_answer,
        )

    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)

    return list(qs.values_list("question_type_id", flat=True))

class PrepScoringFormulaForm(forms.ModelForm):
    class Meta:
        model = PrepScoringFormula
        fields = ["formula", "question_type"]
        widgets = {
            "formula": forms.TextInput(attrs={"class": "form-control"}),
            "question_type": forms.Select(attrs={
                "class": "form-control",
                "style": "min-width:200px",
            }),
        }

    def __init__(self, *args, **kwargs):
        self.scope = kwargs.pop("scope", None)
        self.exam_pk = kwargs.pop("exam_pk", None)
        self.prep_section = kwargs.pop("prep_section", None)
        self.prep_question = kwargs.pop("prep_question", None)
        self.prep_answer = kwargs.pop("prep_answer", None)

        super().__init__(*args, **kwargs)

        if self.scope in ["exam", "section"]:
            self.fields["question_type"].required = True
        else:
            self.fields["question_type"].required = False

        self._filter_question_type_choices()

    def _filter_question_type_choices(self):
        qs = QuestionType.objects.exclude(code="OPEN")

        existing_qt_ids = get_existing_question_type_ids(
            exam_pk=self.exam_pk,
            scope=self.scope,
            prep_section=self.prep_section,
            prep_question=self.prep_question,
            prep_answer=self.prep_answer,
            exclude_pk=self.instance.pk if self.instance and self.instance.pk else None,
        )

        qs = qs.exclude(pk__in=existing_qt_ids)

        if self.instance and self.instance.pk and self.instance.question_type_id:
            qs = (QuestionType.objects.filter(pk=self.instance.question_type_id) | qs).distinct()

        self.fields["question_type"].queryset = qs.distinct()

    def clean(self):
        cleaned_data = super().clean()
        question_type = cleaned_data.get("question_type")

        if self.scope in ["exam", "section"] and not question_type:
            self.add_error("question_type", "This field is required.")
            return cleaned_data

        if not question_type:
            return cleaned_data

        existing_qt_ids = get_existing_question_type_ids(
            exam_pk=self.exam_pk,
            scope=self.scope,
            prep_section=self.prep_section,
            prep_question=self.prep_question,
            prep_answer=self.prep_answer,
            exclude_pk=self.instance.pk if self.instance and self.instance.pk else None,
        )

        if question_type.pk in existing_qt_ids:
            self.add_error(
                "question_type",
                "A scoring formula already exists for this question type at this level."
            )

        return cleaned_data

class BasePrepScoringFormulaFormSet(BaseModelFormSet):
    def clean(self):
        super().clean()

        seen = set()

        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            question_type = form.cleaned_data.get("question_type")
            formula = form.cleaned_data.get("formula")

            if not question_type or not formula:
                continue

            key = question_type.pk
            if key in seen:
                form.add_error(
                    "question_type",
                    "This question type is already used in another row."
                )
            seen.add(key)

PrepScoringFormulaFormSet = modelformset_factory(PrepScoringFormula, form=PrepScoringFormulaForm, formset=BasePrepScoringFormulaFormSet, extra=0)