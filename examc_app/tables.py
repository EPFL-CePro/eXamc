import django_tables2 as tables
from django.urls import reverse
from django.utils.html import format_html

from .models import Exam, ExamUser


class ExamSelectTable(tables.Table):
    id = tables.Column(verbose_name='')

    #extra columns
    #exam_id = tables.Column({{ record.pk}},visible=True)#<a class="btn btn-success btn-sm" href="{% url \'select_exam\' record.pk %}">exam_idxx</a>')
    commons = tables.Column(empty_values=())
    teachers = tables.Column(empty_values=())


    def render_id(self, value):
        text = format_html('<a hidden>{url}</a>',url=reverse('examInfo', kwargs={'exam_pk':str(value)}))
        return text

    def render_commons(self, record):
        return_str = ''
        commons = record.common_exams.all()
        if commons:
            for common in commons:
                if not common.overall:
                    if return_str:
                        return_str += ','
                    return_str += common.code

        return return_str

    def render_teachers(self, record):
        return_str = ''
        exam_users = ExamUser.objects.filter(exam=record,group__pk=2)
        if exam_users:
            for exam_user in exam_users.all():
                if return_str:
                    return_str += ','
                return_str += exam_user.user.first_name + " " + exam_user.user.last_name
        return return_str

    def render_semester(self, record):
        return record.semester.code

    def render_year(self, record):
        return record.year.code

    def before_render(self, request):
        self.columns.hide('id')

    class Meta:
        model = Exam
        template_name = "django_tables2/bootstrap4.html"
        attrs = {"class": "table table-striped table-sm", "id":"select_exam_table_id"}
        fields = ("id","code", "name", "year", "semester", "date", "teachers", "select")
