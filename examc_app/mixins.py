# examc_app/mixins.py
from django.contrib.auth.mixins import AccessMixin
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
from django.shortcuts import get_object_or_404, redirect
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.template.response import TemplateResponse
from django.urls import reverse

from .models import Exam, ExamUser


class ExamPermissionAndRedirectMixin(AccessMixin):
    """
    If redirect_enabled=True: do manage→review→results branching.
    Otherwise: enforce exactly module_codename.

    CBV mixin. Configure:
      exam_kw          = "exam_pk"      # URL kwarg for the exam’s PK
      perm_codename  = "manage"         # URL kwarg for permission codenames # e.g. ["manage","review"]
    """
    perm_codenames: list = None
    exam_kw: str = "exam_pk"
    redirect_enabled: bool = False

    def dispatch(self, request, *args, **kwargs):
        # 1) load exam
        exam = get_object_or_404(Exam, pk=kwargs.get(self.exam_kw))

        # 1x) admin skip checks
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        elif request.user.is_anonymous:
            return self._no_access("You are not an authenticated user.")

        # 2) collect this user’s groups for the exam
        group_ids = ExamUser.objects.filter(
            user=request.user, exam=exam
        ).values_list("group_id", flat=True)

        # 3) check if common exam and teacher and add
        if exam.common_exams.all():
            group_ids_common = ExamUser.objects.filter(
                user=request.user, exam__in=exam.common_exams.all(), group__id__in=[2,5,6]
            )
            group_ids = group_ids.union(group_ids_common)

        # if they don't even belong to this exam
        if not group_ids:
            return self._no_access("You have no access to this exam.")

        # helper to test any codename
        def has(codename_list):
            ct = ContentType.objects.get_for_model(Exam)
            perm = Permission.objects.filter(
                content_type=ct,
                codename__in=codename_list,
                group__id__in=group_ids
            )
            return perm.exists()

        # 3a) Redirect mode (ExamInfoView)
        if self.redirect_enabled:
            # manage → let them in
            if has(['manage']):
                self.exam = exam
                return super().dispatch(request, *args, **kwargs)
            # next‐best fallbacks
            if has(['review']):
                return redirect(reverse('reviewView', kwargs={'exam_pk': exam.pk}))
            if has(['see_results']):
                return redirect(reverse('studentResults', kwargs={'exam_pk': exam.pk}))
            # nothing else
            return self._no_access("You don’t have access to this exam.")

        # 3b) Strict‐check mode (all other views)
        if self.perm_codenames and has(self.perm_codenames):
            self.exam = exam
            return super().dispatch(request, *args, **kwargs)

        return self._no_access(f"No permission for '{self.perm_codenames}'.")

    def _no_access(self, msg):
        # not authenticated?
        if not self.request.user.is_authenticated:
            return self.handle_no_permission()
        # hide whether exam exists
        return TemplateResponse(self.request, "no_access.html",{"message": msg}, status=403)
