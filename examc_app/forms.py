import logging
import os

from django import forms
from django.forms import modelformset_factory, ModelForm
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
    PagesGroup, form=ManagePagesGroupsForm, extra=0
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
    exportIsaCsv = forms.BooleanField(label='export ISA .csv', label_suffix=' ', initial=False, required=False,
                                      widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))
    exportExamScalePdf = forms.BooleanField(label='export Exam scale pdf', label_suffix=' ', initial=False,
                                            required=False,
                                            widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))
    exportStudentsDataCsv = forms.BooleanField(label='export Students data .csv', label_suffix=' ', initial=False,
                                               required=False,
                                               widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))

    def __init__(self, *args, **kwargs):

        EXAM = kwargs.pop('exam', None)

        super(ExportResultsForm, self).__init__(*args, **kwargs)

        if EXAM and EXAM.scaleStatistics:

            if EXAM.overall:
                self.fields['common_exams'] = forms.MultipleChoiceField(
                    widget=forms.CheckboxSelectMultiple(attrs={'class': "custom-radio-list form-check-inline"}),
                    choices=[(c.pk, c.code + " " + c.primary_user.last_name) for c in EXAM.common_exams.all()],
                    required=False)

            self.fields['scale'].choices = [(s.pk, s.name) for s in EXAM.scales.all()]

    scale = forms.ChoiceField(choices=(),
                              widget=forms.RadioSelect(attrs={'class': "custom-radio-list form-check-inline"}),
                              required=True)


# IMAGE_CHOICES = [
#     ('AAC_120.jpg', 'AAC_120.jpg'),
#     ('AAC_132.jpg', 'AAC_132.jpg'),
#     ('AAC_137.jpg', 'AAC_137.jpg'),
#     ('AAC_231.jpg', 'AAC_231.jpg'),
#     ('BCH_2201.jpg', 'AAC_120.jpg'),
#     ('BS_150.jpg', 'BS_150.jpg'),
#     ('BS_160.jpg', 'BS_160.jpg'),
#     ('BS_170.jpg', 'BS_170.jpg'),
#     ('BS_260.jpg', 'BS_260.jpg'),
#     ('BS_270.jpg', 'BS_270.jpg'),
#     ('CE_1_1.jpg', 'CE_1_1.jpg'),
#     ('CE_1_2.jpg', 'CE_1_2.jpg'),
#     ('CE_1_3.jpg', 'CE_1_3.jpg'),
#     ('CE_1_4.jpg', 'CE_1_4.jpg'),
#     ('CE_1_5.jpg', 'CE_1_5.jpg'),
#     ('CE_1_6.jpg', 'CE_1_6.jpg'),
#     ('CE_1100.jpg', 'CE_1100.jpg'),
#     ('CE_1101.jpg', 'CE_1101.jpg'),
#     ('CE_1104.jpg', 'CE_1104.jpg'),
#     ('CE_1105.jpg', 'CE_1105.jpg'),
#     ('CE_1106.jpg', 'CE_1106.jpg'),
#     ('CE_1515_haut.jpg', 'CE_1515_haut.jpg'),
#     ('CE_1515_bas.jpg', 'CE_1515_bas.jpg'),
#     ('CH_B3_30.jpg', 'CH_B3_30.jpg'),
#     ('CM_1_1.jpg', 'CM_1_1.jpg'),
#     ('CM_1_2.jpg', 'CM_1_2.jpg'),
#     ('CM_1_3.jpg', 'CM_1_3.jpg'),
#     ('CM_1_4.jpg', 'CM_1_4.jpg'),
#     ('CM_1_5.jpg', 'CM_1_5.jpg'),
#     ('CM_1106.jpg', 'CM_1106.jpg'),
#     ('CM_1120.jpg', 'CM_1120.jpg'),
#     ('CM_1121.jpg', 'CM_1121.jpg'),
#     ('CO_01.jpg', 'CO_01.jpg'),
#     ('CO_02.jpg', 'CO_02.jpg'),
#     ('CO_03.jpg', 'CO_03.jpg'),
#     ('INJ_218.jpg', 'INJ_218.jpg'),
#     ('MA_A1_10.jpg', 'MA_A1_10.jpg'),
#     ('MA_A1_12.jpg', 'MA_A1_12.jpg'),
#     ('MA_A3_30.jpg', 'MA_A3_30.jpg'),
#     ('MA_A3_31.jpg', 'MA_A3_31.jpg'),
#     ('MA_B1_11.jpg', 'MA_B1_11.jpg'),
#     ('PO_01_exam.jpg', 'PO_01_exam.jpg'),
#     ('PO_01_old.jpg', 'PO_01_old.jpg'),
#     ('SG_0211.jpg', 'SG_0211.jpg'),
#     ('SG_0213.jpg', 'SG_0213.jpg'),
#     ('SG_1138.jpg', 'SG_1138.jpg'),
#     ('STCC.jpg', 'STCC.jpg'),
#     ('STCC_mark.jpg', 'STCC_mark.jpg'),
# ]


# CSV_CHOICES = [
#     ('CE_1_1.csv', 'CE_1_1.csv'),
#     ('CE_1_3.csv', 'CE_1_3.csv'),
#     ('CE_1515_bas.csv', 'CE_1515_bas.csv'),
#     ('BS_160.csv', 'BS_160.csv'),
# ]
CSV_DIR = 'examc_app/scripts/csv/'
JPG_DIR = 'examc_app/scripts/map/'
CSV_FILES = sorted([(f, f) for f in os.listdir(CSV_DIR) if f.endswith('.csv')])
IMAGE_FILES = sorted([(f, f) for f in os.listdir(JPG_DIR) if f.endswith('.jpg')])


class SeatingForm(forms.Form):
    # image_file = forms.ChoiceField(choices=IMAGE_FILES, label='Image file name',
    #                                widget=forms.Select(attrs={'id': 'id_image_file'}))
    csv_file = forms.MultipleChoiceField(choices=CSV_FILES, label='Room',
                                         widget=forms.SelectMultiple(attrs={'id': 'id_csv_file', 'class': "selectpicker form-control",'size':5, 'data-live-search':"true"}))
    # export_file = forms.CharField(label='Export file name', widget=forms.TextInput(attrs={'id': 'id_export_file'}))
    numbering_option = forms.ChoiceField(choices=[('continuous', 'continuous'), ('special', 'special')],
                                         label='Numbering option',
                                         widget=forms.RadioSelect(
                                             attrs={'onchange': "showHideSpecialFile(this.value);"}))
    skipping_option = forms.ChoiceField(choices=[('noskip', 'no skip'), ('skip', 'skip')], label='Skip option',
                                        widget=forms.RadioSelect(attrs={'onchange': "showHideSpecialFile(this.value)", 'id': 'id_skipping_option'}))
    first_seat_number = forms.IntegerField(label='First seat number',
                                           widget=forms.NumberInput(attrs={'id': 'id_first_seat_number'}))
    last_seat_number = forms.IntegerField(label='Last seat number',
                                          widget=forms.NumberInput(attrs={'id': 'id_last_seat_number'}))
    special_file = forms.CharField(label='File name for special number to add or to skip', required=False,
                                   widget=forms.TextInput(attrs={'id': 'id_special_file'}))
    shape_to_draw = forms.ChoiceField(choices=[('circle', 'circle'), ('square', 'square'), ('other', 'other')],
                                      label='Shape to draw',
                                      widget=forms.RadioSelect(attrs={'id': 'id_shape_to_draw'}))
