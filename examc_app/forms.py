from django import forms
import logging
import os

from django.core.exceptions import ValidationError
from django.forms import modelformset_factory, ModelForm
from django_ckeditor_5.widgets import CKEditor5Widget

from .models import PagesGroup, Reviewer, Exam, AcademicYear, Semester, Course, QuestionType
from .utils.global_functions import get_course_teachers_string

from examc import settings
from .models import PagesGroup, Reviewer, Exam


class UploadScansForm(forms.Form):
    files = forms.FileField(widget=forms.ClearableFileInput(attrs={'allow_multiple_selected': True}))


class ManagePagesGroupsForm(forms.ModelForm):
    class Meta:
        model = PagesGroup
        fields = ['group_name', 'page_from', 'page_to']

    def __init__(self, *args, **kwargs):
        super(ManagePagesGroupsForm, self).__init__(*args, **kwargs)
        # you can iterate all fields here
        for fname, f in self.fields.items():
            f.widget.attrs['class'] = 'form-control'
            if fname == 'group_name':
                f.widget.attrs['style'] = 'width:300px;'
            else:
                f.widget.attrs['style'] = 'width:100px;'


PagesGroupsFormSet = modelformset_factory(
    PagesGroup, form=ManagePagesGroupsForm,  extra=0
)


class ManageReviewersForm(forms.ModelForm):
    class Meta:
        model = Reviewer
        fields = ['user', 'pages_groups']

    def __init__(self, *args, **kwargs):
        super(ManageReviewersForm, self).__init__(*args, **kwargs)
        # you can iterate all fields here
        for fname, f in self.fields.items():
            f.widget.attrs['style'] = 'width:300px;'
            f.widget.attrs['class'] = 'form-control'
            if fname == 'user':
                f.disabled = True


ReviewersFormSet = modelformset_factory(Reviewer, form=ManageReviewersForm, extra=0)


class ExportMarkedFilesForm(forms.Form):
    export_type = forms.ChoiceField(widget=forms.RadioSelect,
                                    choices=[(1, 'JPGs (one per page)'), (2, 'PDFs (one per student copy)')],
                                    required=True)

    def __init__(self, *args, **kwargs):
        exam = kwargs.pop('exam', None)

        super(ExportMarkedFilesForm, self).__init__(*args, **kwargs)


class LoginForm(forms.Form):
    username = forms.CharField(max_length=65)
    password = forms.CharField(max_length=65, widget=forms.PasswordInput)

class ExportResultsForm(forms.Form):

    exportIsaCsv = forms.BooleanField(label='export ISA .csv', label_suffix=' ',initial=False, required=False, widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))
    exportExamScalePdf = forms.BooleanField(label='export Exam scale pdf', label_suffix=' ',initial=False, required=False,widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))
    exportStudentsDataCsv = forms.BooleanField(label='export Students data .csv', label_suffix=' ',initial=False, required=False,widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))

    def __init__(self, *args, **kwargs):

        exam = kwargs.pop('exam', None)

        super(ExportResultsForm, self).__init__(*args, **kwargs)

        if exam and exam.scaleStatistics:

            if exam.overall:
                self.fields['common_exams'] = forms.MultipleChoiceField(
                        widget=forms.CheckboxSelectMultiple(attrs={'class': "custom-radio-list form-check-inline"}),
                        choices=[ (c.pk,c.code+" "+c.primary_user.last_name) for c in exam.common_exams.all()],required=False)

            self.fields['scale'].choices=[ (s.pk, s.name) for s in exam.scales.all()]

CSV_DIR = str(settings.ROOMS_PLANS_ROOT) + "/csv/"
JPG_DIR = str(settings.ROOMS_PLANS_ROOT) + "/map/"
CSV_FILES = sorted([(f, f) for f in os.listdir(CSV_DIR) if f.endswith('.csv')])
IMAGE_FILES = sorted([(f, f) for f in os.listdir(JPG_DIR) if f.endswith('.jpg')])

class CreateExamProjectForm(forms.Form):
    # courses to init from new table like ceproexamsmgt!
    COURSES_CHOICES =[(course.pk, course.code+" - "+course.name+" ("+get_course_teachers_string(course.teachers)+")") for course in Course.objects.all().order_by("code")]
    SEMESTER_CHOICES = [ (semester.pk, semester.code) for semester in Semester.objects.all()]
    YEAR_CHOICES = [ (year.pk, year.code) for year in AcademicYear.objects.all().order_by("-code")]

    course = forms.ChoiceField(label='Course',choices=COURSES_CHOICES,widget=forms.Select(attrs={'class': "selectpicker form-control",'size':5, 'data-live-search':"true"}),required=True)
    semester = forms.ChoiceField(label='Language', widget=forms.RadioSelect(attrs={'class': "custom-radio-list"}), choices=SEMESTER_CHOICES, required=True)
    year = forms.ChoiceField(label='Year', choices=YEAR_CHOICES,widget=forms.Select(attrs={'class': "selectpicker form-control",'size':5}),required=True)
    date = forms.DateField(label='Date',widget=forms.DateInput(format=('%d-%m-%Y'), attrs={'id':'dateAndTime','type': 'date','class':'form-control'}),required=True)
    durationText = forms.CharField(label='DurationTxt', widget=forms.TextInput(attrs={'class':'form-control'}),required=True)
    language = forms.ChoiceField(label='Language', widget=forms.RadioSelect(attrs={'class': "custom-radio-list"}),
                      choices=[('fr','FR'),('en','EN')],
                      required=True)

    def clean(self):
        cd = self.cleaned_data
        semester = Semester.objects.get(pk=cd.get("semester"))
        year = AcademicYear.objects.get(pk=cd.get("year"))
        course = Course.objects.get(pk=cd.get("course"))
        exam = Exam.objects.filter(code=course.code,year=year, semester=semester).first()
        if exam:
            if exam.date == cd.get("date"):
                raise ValidationError("Exam for this year, semester and date already exists !")

        return cd

class CreateQuestionForm(forms.Form):
    QUESTION_TYPES_CHOICES = [(qt.pk, qt.code+" - "+qt.name) for qt in QuestionType.objects.all()]

    question_type = forms.ChoiceField(label='Question Type', widget=forms.RadioSelect(attrs={'class': "custom-radio-list",'id':"question_type_choice_create"}), choices=QUESTION_TYPES_CHOICES, required=True,initial=1)
    nb_answers = forms.IntegerField(label='Answers', widget=forms.NumberInput(attrs={'class': "form-control",'id':"nb_answers_create"}),required=False,min_value=1)
    open_max_points = forms.DecimalField(label='Open Max Points', widget=forms.NumberInput(attrs={'class': "form-control",'id':"open_max_points_create"}),required=False,min_value=0.5,initial=1,step_size=0.5)
    open_points_increment = forms.ChoiceField(label='Increment for open points', widget=forms.RadioSelect(attrs={'class': "custom-radio-list",'id':"open_points_increment_create"}), choices=[(0.5,"0.5pt"),(1,"1pt")], required=False,initial=1)
    section_pk = forms.CharField(widget=forms.HiddenInput(),required=False)

    def __init__(self, *args, section_pk=None, **kwargs):
        super(CreateQuestionForm, self).__init__(*args, **kwargs)
        self.fields['section_pk'].initial = section_pk

class ckeditorForm(forms.Form):
    ckeditor_txt = forms.CharField(widget=CKEditor5Widget(attrs={'class':'django_ckeditor_5','width': '100%'}))

class SeatingForm(forms.Form):
    csv_file = forms.MultipleChoiceField(
        choices=CSV_FILES,
        label='Room',
        help_text="Select one or more rooms. The room order is the alphabetic one",
        widget=forms.SelectMultiple(
            attrs={
                "data-tooltip-location": "top",
                'id': 'id_csv_file',
                'class': "selectpicker form-control",
                'size': 5,
                'data-live-search': "true"
            }
        )
    )

    numbering_option = forms.ChoiceField(
        choices=[('continuous', 'Continuous'), ('special', 'Special')],
        label='Numbering Option',
        help_text="Select how seats are numbered. The special option is used for student needs. Upload a .csv with "
                  "the special numbers. Fill in the first and last number then download. The numbers will be the one "
                  "that are in the special file.",
        widget=forms.RadioSelect(attrs={'onchange': "showHideSpecialFile(this.value);"}),
        initial='continuous'
    )

    skipping_option = forms.ChoiceField(
        choices=[('noskip', 'No skip'), ('skip', 'Skip')],
        label='Skip Option',
        help_text="Choose whether to skip seats. Upload a .csv with the numbers to skip.",
        widget=forms.RadioSelect(attrs={'onchange': "showHideSpecialFile(this.value)", 'id': 'id_skipping_option'}),
        initial='noskip'
    )

    fill_all_seats = forms.BooleanField(
        required=False,
        help_text="Fill all seats of the plans from the first number to the end of the plan.",
        widget=forms.CheckboxInput(attrs={'id': 'id_fill_all_seats', 'onchange': "showHideLastNumber(this.checked)"})
    )

    first_seat_number = forms.IntegerField(
        label='First Seat Number',
        help_text="Enter the starting seat number.",
        widget=forms.NumberInput(attrs={'id': 'id_first_seat_number'}),
        required=False
    )

    last_seat_number = forms.IntegerField(
        label='Last Seat Number',
        help_text="Enter the last seat number.",
        widget=forms.NumberInput(attrs={'id': 'id_last_seat_number'}),
        required=False
    )

    special_file = forms.FileField(
        label='Special File',
        required=False,
        help_text="Upload a file for special seat numbers or skipping. A CSV file with all the numbers you want to skip or add.",
        widget=forms.ClearableFileInput(attrs={'id': 'id_special_file'})
    )

    shape_to_draw = forms.ChoiceField(
        choices=[('circle', 'Circle'), ('square', 'Square')],
        label='Shape to Draw',
        help_text="Choose the shape to numbering.",
        widget=forms.RadioSelect(attrs={'data-tooltip': "Choose the shape to draw."}),
        initial='circle'
    )
    # preview = forms.BooleanField(required=False, initial=False, widget=forms.HiddenInput())
