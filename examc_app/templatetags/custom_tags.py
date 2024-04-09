from django import template
from django.contrib.auth.models import User
from django.utils.safestring import mark_safe



register = template.Library()

@register.filter
def get_number_of_pages(group_name,scan_pathes_list):
    return len(scan_pathes_list[group_name])

@register.filter
def is_reviewer(user,exam):
    auth_user = User.objects.get(username=user.username)

    if auth_user in exam.users.all() or auth_user.is_superuser:
        return False
    else:
        for exam_reviewer in exam.examReviewers.all():
            if auth_user == exam_reviewer.user:
                return True

    return False
