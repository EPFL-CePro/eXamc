from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django_summernote.widgets import SummernoteWidget

from examc_app.models import Exam, Semester


class LoginForm(forms.Form):
    username = forms.CharField(max_length=65)
    password = forms.CharField(max_length=65, widget=forms.PasswordInput)

class SwitchWidget(forms.CheckboxInput):
    def render(self, name, value, attrs=None, renderer=None):
        attrs = {**(attrs or {})}
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

class SummernoteForm(forms.Form):
    summernote_txt = forms.CharField(
        widget=SummernoteWidget(
            attrs={'summernote': {'width': '100%', 'height': '300px'}}
        )
    )