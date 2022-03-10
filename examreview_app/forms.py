import logging

from django import forms

class UploadScansForm(forms.Form):
files = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))
