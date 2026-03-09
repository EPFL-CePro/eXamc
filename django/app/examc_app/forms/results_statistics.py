from django import forms
from django.utils.safestring import mark_safe


class ExportMarkedFilesForm(forms.Form):
    export_type = forms.ChoiceField(widget=forms.RadioSelect,
                                    choices=[(2, 'PDFs (one per student copy)'),(1, 'JPGs (one per page)')],
                                    initial=2,
                                    required=True)

    with_comments = forms.ChoiceField(widget=forms.RadioSelect,
                                      choices=[(1,'Yes'),(2,'No')],
                                      initial=1,
                                      required=True)

    def __init__(self, *args, **kwargs):
        exam = kwargs.pop('exam', None)

        super(ExportMarkedFilesForm, self).__init__(*args, **kwargs)




class ExportResultsForm(forms.Form):

    exportIsaCsv = forms.BooleanField(label='export ISA .csv', label_suffix=' ',initial=False, required=False, widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))
    exportExamScalePdf = forms.BooleanField(label='export Exam scale pdf', label_suffix=' ',initial=False, required=False,widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))
    exportStudentsDataCsv = forms.BooleanField(label='export Students data .csv', label_suffix=' ',initial=False, required=False,widget=forms.CheckboxInput(attrs={'class': "form-check-input"}))
    scale = forms.ChoiceField(choices=(), widget=forms.RadioSelect(attrs={'class': "custom-radio-list form-check-inline"}), required=True)
    def __init__(self, *args, **kwargs):

        exam = kwargs.pop('exam', None)

        super(ExportResultsForm, self).__init__(*args, **kwargs)

        if exam and exam.scaleStatistics:

            if exam.overall:
                self.fields['common_exams'] = forms.MultipleChoiceField(
                        widget=forms.CheckboxSelectMultiple(attrs={'class': "custom-radio-list form-check-inline"}),
                        choices=[ (c.pk,c.code+" "+c.exam_users.first().user.last_name) for c in exam.common_exams.all()],required=False)
            choices = []
            for s in exam.scales.all():
                text = s.name
                if s.final:
                    text = s.name +' <i class="fa-solid fa-circle-check fa-xs"></i>'
                choices.append((s.pk, mark_safe(text)))

            self.fields['scale'].choices=choices#[ (s.pk, s.name) for s in exam.scales.all()]