from functools import wraps

from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse

from .models import Exam
from .permissions import exam_group_names_allow, get_exam_group_names


def _forbidden_response(request: HttpRequest, message:str) -> TemplateResponse:
    return TemplateResponse(request, "unauthorized.html", {"message": message}, status=403)

def exam_permission_required(
        perm_codenames: list,
        *,
        exam_kw: str = "exam_pk"
):
    """
    Restrict a view to users holding one of `perm_codenames` on the exam.

    The exam is exposed as `request.exam`, so the view does not need to query it again.

    Responses:
        403 if the user is anonymous, has no group on the exam, or lacks the permission.
        404 if the exam does not exist
        Superusers skip the permission check.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.is_anonymous:
                return _forbidden_response(request, message="Authentication required to access this exam.")

            exam = get_object_or_404(Exam, pk=kwargs.get(exam_kw))

            if request.user.is_superuser:
                request.exam = exam
                return view_func(request, *args, **kwargs)

            # fetch the user's groups *for this exam*
            group_names = get_exam_group_names(request.user, exam)
            if not group_names:
                return _forbidden_response(request, message="No access to this exam.")

            # check the permission on one of those groups
            if not exam_group_names_allow(group_names, perm_codenames):
                return _forbidden_response(request, message=f"No permission for {perm_codenames}.")

            request.exam = exam
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator
