from django.contrib import admin
from .models import *
from simple_history.admin import SimpleHistoryAdmin

# Register your models here.

admin.site.register(Exam,SimpleHistoryAdmin)
admin.site.register(ExamPagesGroup,SimpleHistoryAdmin)
admin.site.register(ExamPagesGroupComment,SimpleHistoryAdmin)
admin.site.register(ExamReviewer,SimpleHistoryAdmin)
admin.site.register(ScanMarkers,SimpleHistoryAdmin)