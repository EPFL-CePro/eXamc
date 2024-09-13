from django import forms
from django.contrib import admin
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html
from import_export.admin import ImportExportModelAdmin
from simple_history.admin import SimpleHistoryAdmin

from .models import *
from .models import Exam
from .utils.admin_functions import parse_exams_data_csv, parse_courses_data_json


class CsvImportForm(forms.Form):
    csv_file = forms.FileField()

class JsonImportForm(forms.Form):
    json_file = forms.FileField()


@admin.register(Exam)
class ExamAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ["code", "name", "semester", "year",'show_commons', 'get_common_exams_button']
    filter_horizontal = ('common_exams',)

    def show_commons(self, obj):
            return_str = ''
            commons = obj.common_exams.all()
            if commons:
                for common in commons:
                    if return_str:
                        return_str += ','
                    return_str += common.code
            return return_str

    def getCommonExams(self, request, obj):
        return obj.getCommonExams

        pass

    def get_common_exams_button(self, obj):
        html_str = format_html('<a href="{0}">Get common exams</a>',reverse('getCommonExams', kwargs={'pk':obj.pk}))
        logger.info(html_str)
        return html_str

    get_common_exams_button.short_description = 'Action'
    get_common_exams_button.allow_tags = True

    def import_exams_csv_data(self, request):
        if request.method == 'POST':
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                csv_file = request.FILES['csv_file']
                result = parse_exams_data_csv(csv_file)

                if not result == 'ok' :
                    print(result)
        else:
            form = CsvImportForm()
        return render(request, "admin/import_exams.html", {"form": form})
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('import/', self.import_exams_csv_data),
        ]
        return my_urls + urls

@admin.register(Course)
class CourseAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ["code", "name", "semester", "year","teachers"]
    def import_courses_json_data(self, request):
        if request.method == 'POST':
            form = JsonImportForm(request.POST, request.FILES)
            if form.is_valid():
                json_file = request.FILES['json_file']
                json_data = json_file.read()
                result = parse_courses_data_json(json_data)

                if not result == 'ok' :
                    print(result)
        else:
            form = JsonImportForm()
        return render(request, "admin/import_courses.html", {"form": form})
    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('import/', self.import_courses_json_data),
        ]
        return my_urls + urls

admin.site.register(PagesGroup, SimpleHistoryAdmin)
admin.site.register(PagesGroupComment, SimpleHistoryAdmin)
admin.site.register(ExamUser, SimpleHistoryAdmin)
admin.site.register(PageMarkers, SimpleHistoryAdmin)
admin.site.register(Question)
admin.site.register(Student)
admin.site.register(Scale)
admin.site.register(Semester)
admin.site.register(AcademicYear)
admin.site.register(ExamSection, SimpleHistoryAdmin)
admin.site.register(QuestionAnswer, SimpleHistoryAdmin)
