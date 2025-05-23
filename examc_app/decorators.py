# examc_app/decorators.py
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponseForbidden, Http404
from django.template.response import TemplateResponse
from django.urls import reverse

from .models import Exam, ExamUser

# def is_admin(function):
#     def wrapper(request, *args, **kwargs):
#         if request.user.groups.filter(name="admin").exists():
#             return function(request, *args, **kwargs)
#         raise Http404
#
#     return wrapper

def exam_permission_required(
    perm_codenames: list,
    *,
    exam_kw: str = "exam_pk"
):
    """
    Strict mode: check exactly perm_codename on the exam.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            exam = get_object_or_404(Exam, pk=kwargs.get(exam_kw))

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            # fetch the user’s groups *for this exam*
            group_ids = ExamUser.objects.filter(
                user=request.user, exam=exam
            ).values_list("group_id", flat=True)

            if exam.common_exams.all():
                group_ids_common = ExamUser.objects.filter(
                    user=request.user, exam__in=exam.common_exams.all(), group__id__in=[2, 5, 6]
                )
                group_ids = group_ids.union(group_ids_common)

            if not group_ids:
                return TemplateResponse(request, "no_access.html", {"message": "No access to this exam."}, status=403)

            # check the permission on one of those groups
            ct = ContentType.objects.get_for_model(Exam)
            allowed = Permission.objects.filter(
                content_type=ct,
                codename__in=perm_codenames,
                group__id__in=group_ids
            ).exists()

            if not allowed:
                return TemplateResponse(request, "no_access.html", {"message": f"No permission for {perm_codenames}."}, status=403)

            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
