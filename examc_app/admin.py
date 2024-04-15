from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin
from import_export.admin import ImportExportModelAdmin
from django.shortcuts import render
from django import forms

# Register your models here.

admin.site.register(Exam, SimpleHistoryAdmin)
admin.site.register(ExamPagesGroup, SimpleHistoryAdmin)
admin.site.register(ExamPagesGroupComment, SimpleHistoryAdmin)
admin.site.register(ExamReviewer, SimpleHistoryAdmin)
admin.site.register(ScanMarkers, SimpleHistoryAdmin)


# create a form field which can input a file
class CsvImportForm(forms.Form):
    csv_file = forms.FileField()


class ExamsAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    list_display = ("year", "semester", "code", "name", "teacher")

    def import_action(self, request):
        form = CsvImportForm()
        context = {"form": form}
        return render(request, "home.html", context)
