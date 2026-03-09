from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django_summernote.widgets import SummernoteWidget

from examc_app.models import Course, AcademicYear, Semester, Exam
from examc_app.utils.global_functions import get_course_teachers_string


class LoginForm(forms.Form):
    username = forms.CharField(max_length=65)
    password = forms.CharField(max_length=65, widget=forms.PasswordInput)

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
            f'<div class="custom-control custom-switch mb-3" style="width:150px;text-align:center;">'
            f'{checkbox_html}'
            f'{label_html}'
            f'</div>'
        )

class CreateExamProjectForm(forms.Form):
    course = forms.ChoiceField(label='Course', choices=[], widget=forms.Select(
        attrs={'class': "selectpicker form-control", 'size': 5, 'data-live-search': "true"}), required=True)
    semester = forms.ChoiceField(label='Language', widget=forms.RadioSelect(attrs={'class': "custom-radio-list"}),
                                 choices=[], required=True)
    year = forms.ChoiceField(label='Year', choices=[],
                             widget=forms.Select(attrs={'class': "selectpicker form-control", 'size': 5}),
                             required=True)
    date = forms.DateField(label='Date', widget=forms.DateInput(format=('%d-%m-%Y'),
                                                                attrs={'id': 'dateAndTime', 'type': 'date',
                                                                       'class': 'form-control'}), required=True)

    # durationText = forms.CharField(label='DurationTxt', widget=forms.TextInput(attrs={'class':'form-control'}),required=True)
    # language = forms.ChoiceField(label='Language', widget=forms.RadioSelect(attrs={'class': "custom-radio-list"}),
    #                   choices=[('fr','FR'),('en','EN')],
    #                   required=True)

    def __init__(self, *args, **kwargs):
        super(CreateExamProjectForm, self).__init__(*args, **kwargs)

        COURSES_CHOICES = [(course.pk, course.code + " - " + course.name + " (" + get_course_teachers_string(
            course.teachers) + ")") for course in Course.objects.all().order_by("code")]
        SEMESTER_CHOICES = [(semester.pk, semester.code) for semester in Semester.objects.all()]
        YEAR_CHOICES = [(year.pk, year.code) for year in AcademicYear.objects.all().order_by("-code")]

        # Load choices here so db calls are not made during migrations.
        self.fields['course'].choices = COURSES_CHOICES
        self.fields['semester'].choices = SEMESTER_CHOICES
        self.fields['year'].choices = YEAR_CHOICES

    def clean(self):
        cd = self.cleaned_data
        semester = Semester.objects.get(pk=cd.get("semester"))
        year = AcademicYear.objects.get(pk=cd.get("year"))
        course = Course.objects.get(pk=cd.get("course"))
        exam = Exam.objects.filter(code=course.code, year=year, semester=semester).first()
        if exam:
            if exam.date == cd.get("date"):
                raise ValidationError("Exam for this year, semester and date already exists !")

        return cd

class SummernoteForm(forms.Form):
    summernote_txt = forms.CharField(
        widget=SummernoteWidget(
            attrs={'summernote': {'width': '100%', 'height': '300px'}}
        )
    )