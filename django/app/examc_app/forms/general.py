from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django_summernote.widgets import SummernoteWidget

from examc_app.models import Semester, Exam


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
    course = forms.ChoiceField(
        label='Course',
        choices=[],
        widget=forms.Select(attrs={'class': "selectpicker form-control",'size':5, 'data-live-search':"true"}),
        required=True
    )

    semester = forms.ChoiceField(
        label='Semester',
        choices=[],
        widget=forms.RadioSelect(attrs={'class': "custom-radio-list"}),
        required=True
    )

    date = forms.DateField(
        label='Date',
        widget=forms.DateInput(format='%d-%m-%Y', attrs={'id': 'dateAndTime', 'type': 'date', 'class': 'form-control'}),
        required=True
    )

    # durationText = forms.CharField(label='DurationTxt', widget=forms.TextInput(attrs={'class':'form-control'}),required=True)
    # language = forms.ChoiceField(label='Language', widget=forms.RadioSelect(attrs={'class': "custom-radio-list"}),
    #                   choices=[('fr','FR'),('en','EN')],
    #                   required=True)

    def __init__(self, *args, courses, teacher_names_by_course, **kwargs):
        super().__init__(*args, **kwargs)

        self.errors_list = []

        self.courses_by_code = {course["coursCode"]: course for course in courses}
        self.teachers_by_course = teacher_names_by_course

        courses_choices = []

        for course in courses:
            code = course["coursCode"]
            label = f'{code} - {course["coursNomFr"]}'

            course_teachers = teacher_names_by_course.get(code, [])
            if course_teachers:
                label += f" ({', '.join(t['name'] for t in course_teachers)})"

            courses_choices.append((code, label))

        # populate the course field + error mgmt
        self.fields["course"].choices = courses_choices

        if len(courses_choices) == 0:
            self.errors_list.append("No courses are available. Please create a course first.")


        # populate the semester field + error mgmt
        self.fields["semester"].choices = [
            (semester.pk, semester.code)
            for semester in Semester.objects.all()
        ]

        if len(self.fields["semester"].choices) == 0:
            self.errors_list.append("No semesters are available. Please create a semester first.")

    def clean(self):
        cleaned_data = super().clean()

        course_code = cleaned_data.get("course")
        date = cleaned_data.get("date")

        if not course_code or not date:
            return cleaned_data

        if Exam.objects.filter(code=course_code, date=date).exists():
            raise ValidationError(
                "An exam for this course and date already exists."
            )

        return cleaned_data

class SummernoteForm(forms.Form):
    summernote_txt = forms.CharField(
        widget=SummernoteWidget(
            attrs={'summernote': {'width': '100%', 'height': '300px'}}
        )
    )