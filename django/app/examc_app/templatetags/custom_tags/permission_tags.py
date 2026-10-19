from typing import Literal

from django import template
from django.contrib.auth.models import User

from examc_app.models import ExamUser

register = template.Library()


@register.filter
def is_allowed(_user_exam, option: Literal['preparation', 'creation', 'amc', 'res_and_stats', 'review']):
    user, exam = _user_exam
    auth_user = User.objects.get(pk=user.pk)
    if auth_user.is_superuser:
        return True

    group_ids_allowed = []

    if option == 'preparation':
        group_ids_allowed = [2, 4]
    elif option == 'creation':
        return bool(user.groups.filter(pk__in=[1, 2, 4, 5]).exists())
    elif option == 'amc':
        group_ids_allowed = [2, 4]
    elif option == 'res_and_stats':
        group_ids_allowed = [2, 4, 5, 6]
    elif option == 'review':
        group_ids_allowed = [2, 3, 4]

    exam_user = ExamUser.objects.filter(exam=exam, user=auth_user, group__in=group_ids_allowed)

    if not exam_user and exam.common_exams:
        for comex in exam.common_exams.all():
            exam_user = ExamUser.objects.filter(exam=comex, user=auth_user, group__in=group_ids_allowed).first()
            if exam_user:
                break

    return bool(exam_user)


@register.filter
def is_admin(user: User):
    auth_user = User.objects.get(username=user.username)
    return auth_user.is_superuser


@register.filter
def is_review_blocked(user_id, exam_id):
    user = User.objects.get(id=user_id)
    if user.is_superuser:
        return False
    exam_user = ExamUser.objects.get(exam_id=exam_id, user_id=user_id)
    return exam_user.review_blocked