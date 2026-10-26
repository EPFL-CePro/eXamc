from typing import Any, Collection

from django import forms
from django.utils.safestring import mark_safe
from django_summernote.widgets import SummernoteWidget


class SummernoteForm(forms.Form):
    summernote_txt = forms.CharField(
        widget=SummernoteWidget(
            attrs={'summernote': {'width': '100%', 'height': '300px'}}
        )
    )


class ChoiceMixin:
    template_name = "forms/choice_multiple.html"
    option_template_name = "forms/choice_options.html"

    # Used to control whether the choices are displayed inline or not
    inline = False

    def __init__(self, attrs=None, choices=(), inline=None):
        if inline is not None:
            self.inline = inline
        attrs = {"class": "form-check-input", **(attrs or {})}
        super().__init__(attrs, choices)

    def create_option(self, *args, **kwargs):
        option = super().create_option(*args, **kwargs)
        option["inline"] = self.inline
        return option

class RadioSelect(ChoiceMixin, forms.RadioSelect):
    pass


class CheckboxSelectMultiple(ChoiceMixin, forms.CheckboxSelectMultiple):
    pass


class InlineRadioSelect(RadioSelect):
    inline = True


class InlineCheckboxSelectMultiple(CheckboxSelectMultiple):
    inline = True


class SwitchWidget(forms.CheckboxInput):
    def render(self, name, value, attrs=None, renderer=None):
        if attrs is None: attrs = {}

        attrs['class'] = f"{attrs.get('class', '')} form-check-input".strip()
        attrs['role'] = 'switch'
        if 'id' not in attrs:
            attrs['id'] = f'id_{name}'
        checkbox_html = super().render(name, value, attrs, renderer)

        return mark_safe(
            f'<div class="form-check form-switch" style="text-align:center; width: fit-content">'
            f'<label class="form-check-label" for="{attrs["id"]}">{checkbox_html}</label>'
            f'</div>'
        )


class SelectWithDisabledOptions(forms.Select):
    """A select whose options with one of the given values are disabled, unless selected."""

    def __init__(self, *args: Any, disabled_values: Collection[str] = (), **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.disabled_values: set[str] = set(disabled_values)

    def create_option(
        self,
        name: str,
        value: Any,
        label: str | int,
        selected: bool,
        index: int,
        subindex: int | None = None,
        attrs: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        option: dict[str, Any] = super().create_option(name, value, label, selected, index, subindex, attrs)
        if not selected and str(value) in self.disabled_values:
            option["attrs"]["disabled"] = True
        return option