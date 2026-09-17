from typing import Iterable, TypeAlias

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models.query import QuerySet

from examc_app.models import ExamUser, Exam


GroupNames: TypeAlias = str | Iterable[str] | None

def _normalize_group_names(group_names: GroupNames) -> set[str]:
    if group_names is None: return set()

    if isinstance(group_names, str):
        group_names = (group_names,)

    return {
        group_name.strip().casefold()
        for group_name in group_names
        if group_name and group_name.strip()
    }


def _get_configured_permission_group_names() -> dict[str, set[str]]:
    return {
        codename: _normalize_group_names(group_names)
        for codename, group_names in getattr(settings, "EXAM_PERMISSION_GROUP_NAMES", {}).items()
    }


def _get_common_exam_group_names() -> set[str]:
    return _normalize_group_names(getattr(settings, "COMMON_EXAM_GROUP_NAMES", ()))


def _get_exam_user_group_names(queryset: QuerySet[ExamUser]) -> set[str]:
    return _normalize_group_names(
        queryset.filter(group__isnull=False).values_list("group__name", flat=True)
    )


def get_exam_group_names(user: User, exam: Exam) -> set[str]:
    group_names = _get_exam_user_group_names(
        ExamUser.objects.filter(
            user=user,
            exam=exam,
        )
    )

    if exam.common_exams.exists():
        common_exam_group_names = _get_exam_user_group_names(
            ExamUser.objects.filter(
                user=user,
                exam__in=exam.common_exams.all(),
            )
        )
        group_names.update(common_exam_group_names & _get_common_exam_group_names())

    return group_names


def exam_group_names_allow(group_names: GroupNames, permission_codenames: Iterable[str]) -> bool:
    group_names = _normalize_group_names(group_names)
    permission_group_names = _get_configured_permission_group_names()

    for codename in permission_codenames:
        if group_names & permission_group_names.get(codename, set()):
            return True
    return False
