from collections.abc import Callable, Sequence
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar

from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from examc_app.models import Exam
from examc_app.permissions import exam_group_names_allow, get_exam_group_names

P = ParamSpec("P")
V = TypeVar("V", bound=APIView)

Handler = Callable[Concatenate[V, Request, P], Response]


def exam_permission_required(
    perm_codenames: Sequence[str],
    *,
    exam_kw: str = "exam_pk",
) -> Callable[[Handler[V, P]], Handler[V, P]]:
    """
    Strict mode: check exactly perm_codenames on the exam.
    Raises PermissionDenied / Http404, which DRF returns as JSON.
    """
    def decorator(handler: Handler[V, P]) -> Handler[V, P]:
        @wraps(handler)
        def _wrapped(self: V, request: Request, *args: P.args, **kwargs: P.kwargs) -> Response:
            exam = get_object_or_404(Exam, pk=kwargs.get(exam_kw))

            if not request.user.is_superuser:
                # fetch the user's groups *for this exam*
                group_names = get_exam_group_names(request.user, exam)
                if not group_names:
                    raise PermissionDenied("No access to this exam.")

                # check the permission on one of those groups
                if not exam_group_names_allow(group_names, perm_codenames):
                    raise PermissionDenied(f"No permission for {list(perm_codenames)}.")

            return handler(self, request, *args, **kwargs)
        return _wrapped
    return decorator