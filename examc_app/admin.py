import csv
from django import forms
from django.shortcuts import render
from django.urls import path, reverse
from django.utils.html import format_html

from .models import *
from simple_history.admin import SimpleHistoryAdmin
from django.contrib.auth.models import User, Group
from .models import Exam
from import_export.admin import ImportExportModelAdmin
from django.contrib import admin


class CsvImportForm(forms.Form):
    csv_file = forms.FileField()


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

    def import_csv_data(self, request):
        if request.method == 'POST':
            form = CsvImportForm(request.POST, request.FILES)
            if form.is_valid():
                try:
                    csv_file = request.FILES['csv_file']
                    csv_reader = csv.reader(csv_file.read().decode('utf-8').splitlines(), delimiter=',')

                    headers = next(csv_reader)

                    for row in csv_reader:
                        code_index = headers.index('CODE')
                        name_index = headers.index('NAME')
                        semester_index = headers.index('SEMESTER')
                        year_index = headers.index('YEAR')
                        sciper_index = headers.index('SCIPER')
                        firstname_index = headers.index('FIRSTNAME')
                        lastname_index = headers.index('LASTNAME')
                        email_index = headers.index('EMAIL')
                        reviewer_index = headers.index('REVIEWER')

                        code = row[code_index]
                        name = row[name_index]
                        semester = int(row[semester_index])
                        year = int(row[year_index])

                        exam, created = Exam.objects.get_or_create(code=code, defaults={'name': name, 'semester': semester, 'year': year} )
                        if created:
                            exam.save()

                        user_sciper = row[sciper_index]
                        user_firstname = row[firstname_index]
                        user_lastname = row[lastname_index]
                        user_email = row[email_index]
                        user, created_user = User.objects.get_or_create(username=user_sciper, defaults={'first_name': user_firstname, 'last_name': user_lastname, 'email': user_email})

                        if row[reviewer_index] == '1':
                            group_name = "reviewer"
                            reviewer_group = Group.objects.get(name=group_name)
                            reviewer_group.user_set.add(user)
                        else:
                            group_name = "staff"
                            staff_group = Group.objects.get(name=group_name)
                            staff_group.user_set.add(user)

                except Exception as e:
                    print(f"CSV error : {e}")
        else:
            form = CsvImportForm()
        return render(request, "admin/import_exam.html", {"form": form})

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path('import/', self.import_csv_data),
        ]
        return my_urls + urls
#admin.site.register(SimpleHistoryAdmin)

admin.site.register(PagesGroup, SimpleHistoryAdmin)
admin.site.register(PagesGroupComment, SimpleHistoryAdmin)
admin.site.register(Reviewer, SimpleHistoryAdmin)
admin.site.register(PageMarkers, SimpleHistoryAdmin)
admin.site.register(Question)
admin.site.register(Student)
admin.site.register(Scale)
