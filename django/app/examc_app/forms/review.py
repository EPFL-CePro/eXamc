from collections.abc import Collection
from typing import Any, ClassVar

from django import forms
from django.forms import modelformset_factory

from examc_app.forms.general import SelectWithDisabledOptions, SwitchWidget
from examc_app.models import (
    ExamUser,
    PagesGroup,
    QuestionGradingScheme,
    QuestionGradingSchemeCheckBox,
    UnrecognizedReviewScan,
)


class UploadScansForm(forms.Form):
    files = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"allow_multiple_selected": True})
    )



class ManagePagesGroupsForm(forms.ModelForm):
    class Meta:
        model = PagesGroup
        fields: ClassVar = ["group_name", "nb_pages", "use_grading_scheme"]

    def __init__(
        self,
        questions_choices: list[tuple[str, str]],
        *args: Any,
        locked_pages_group_ids: Collection[int] = (),
        used_question_names: Collection[str] = (),
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)

        # A group can keep, or switch back to, its own saved question.
        own_question: str | None = self.instance.group_name if self.instance.pk is not None else None
        taken_by_others: set[str] = set(used_question_names) - {own_question} if own_question else set(used_question_names)
        
        self.fields["group_name"] = forms.ChoiceField(
            label="Question",
            choices=questions_choices,
            widget=SelectWithDisabledOptions(
                attrs={"class": "form-select"},
                disabled_values=taken_by_others,
            ),
            required=True,
        )

        self.fields["nb_pages"] = forms.IntegerField(
            label="Pages",
            widget=forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "style": "width:100px",
                }
            ),
            required=True,
            min_value=1,
        )

        self.fields["use_grading_scheme"] = forms.BooleanField(
            label="Use grading scheme", widget=SwitchWidget(), required=False
        )

        # Locked groups keep their current values: disabled fields ignore submitted data.
        self.locked: bool = self.instance.pk is not None and self.instance.pk in locked_pages_group_ids

        if self.locked:
            for field in self.fields.values():
                field.disabled = True

PagesGroupsFormSet = modelformset_factory(
    PagesGroup, form=ManagePagesGroupsForm, extra=0
)

class ManageReviewersForm(forms.ModelForm):
    # override the field to give it our SwitchWidget
    review_blocked = forms.BooleanField(
        required=False,
        widget=SwitchWidget(),
        label="Block review",
    )

    class Meta:
        model = ExamUser
        fields: ClassVar = ["pages_groups", "review_blocked"]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Only the row's exam's pages groups: without this, every exam's pages groups would be options.
        pages_groups_field = self.fields["pages_groups"]
        if isinstance(pages_groups_field, forms.ModelMultipleChoiceField):
            pages_groups_field.queryset = (
                PagesGroup.objects.filter(exam_id=self.instance.exam_id)
                if self.instance.pk is not None
                else PagesGroup.objects.none()
            )

        pages_groups_field.widget.attrs["class"] = "form-select"

ReviewersFormSet = modelformset_factory(ExamUser, form=ManageReviewersForm, extra=0)

class GradingSchemeForm(forms.ModelForm):
    class Meta:
        model = QuestionGradingScheme
        fields: ClassVar = ["name", "max_points", "description"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for fname, f in self.fields.items():
            f.widget.attrs["class"] = "form-control"
            if fname == "description":
                f.widget.attrs["rows"] = 2
            if fname == "max_points":
                f.widget.attrs["style"] = "width: 9rem"
                f.widget.attrs["readonly"] = True
                f.disabled = True


GradingSchemeFormSet = modelformset_factory(
    QuestionGradingScheme, form=GradingSchemeForm, extra=0
)


class GradingSchemeCheckBoxForm(forms.ModelForm):
    class Meta:
        model = QuestionGradingSchemeCheckBox
        fields: ClassVar = ["name", "points", "description", "position"]
        widgets: ClassVar = {
            "position": forms.HiddenInput(),
            "description": forms.Textarea(attrs={"data-simple-editor": True, "hidden": True}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"class": "form-control", "style": "min-width:300px"})
        self.fields["points"].widget.attrs.update({"class": "form-control", "style": "width: 8rem"})
        # Optional, and hidden behind the simple editor: a required hidden field would block the form's submit
        self.fields["description"].required = False

GradingSchemeCheckboxFormSet = modelformset_factory(
    QuestionGradingSchemeCheckBox, form=GradingSchemeCheckBoxForm, extra=0
)


class DeleteUnrecognizedReviewScansForm(forms.Form):
    scan_ids = forms.ModelMultipleChoiceField(
        queryset=UnrecognizedReviewScan.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, exam, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["scan_ids"].queryset = UnrecognizedReviewScan.objects.filter(
            exam=exam,
            resolved=False,
        ).order_by("pk")
