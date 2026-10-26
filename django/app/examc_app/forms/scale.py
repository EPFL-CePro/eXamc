from typing import Any, ClassVar

from django import forms

from examc_app.models import Scale


class ScaleForm(forms.ModelForm):
    class Meta:
        model = Scale
        fields: ClassVar = ["name", "total_points", "points_to_add", "min_grade", "max_grade", "rounding"]
        labels: ClassVar = {
            "total_points": "Total points",
            "points_to_add": "Points to add",
            "min_grade": "Minimum grade",
            "max_grade": "Maximum grade",
        }
        help_texts: ClassVar = {
            "points_to_add": "Added to every student's points before computing the grade.",
            "rounding": "Precision of the grades, e.g. 0.25 for quarter points.",
        }
        widgets: ClassVar = {
            "name": forms.TextInput(attrs={"placeholder": "e.g. Standard scale"}),
            "total_points": forms.NumberInput(attrs={"step": "any", "min": 0}),
            "points_to_add": forms.NumberInput(attrs={"step": "any"}),
            "min_grade": forms.NumberInput(attrs={"step": "0.25"}),
            "max_grade": forms.NumberInput(attrs={"step": "0.25"}),
            "rounding": forms.NumberInput(attrs={"step": "any", "min": 0}),
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            css = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            field.widget.attrs["class"] = f"{field.widget.attrs.get('class', '')} {css}".strip()

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean()
        min_grade, max_grade = cleaned.get("min_grade"), cleaned.get("max_grade")
        if min_grade is not None and max_grade is not None and min_grade >= max_grade:
            self.add_error("max_grade", "The maximum grade must be above the minimum grade.")
        return cleaned