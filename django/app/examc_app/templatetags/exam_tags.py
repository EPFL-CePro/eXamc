from django import template
from django.db.models import Sum

from examc_app.models import Exam

register = template.Library()


@register.filter
def get_exam_name(exam_pk: int | str) -> str:
    """The name of an exam, from its primary key; '' if there's no such exam."""
    exam = Exam.objects.filter(pk=exam_pk).first()
    return str(exam) if exam else ""

@register.filter
def get_sum_questions_points(exam_id: int | str):
    exam = Exam.objects.get(pk=exam_id)
    return exam.questions.filter(removed_from_common=False).aggregate(Sum('max_points')).get('max_points__sum')
