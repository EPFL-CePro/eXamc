from django.conf import settings

from examc_app.models import ExamUser


def _normalize_group_names(group_names):
    if group_names is None:
        return set()
    if isinstance(group_names, str):
        group_names = (group_names,)
    return {
        group_name.strip().casefold()
        for group_name in group_names
        if group_name and group_name.strip()
    }


def _get_configured_permission_group_names():
    return {
        codename: _normalize_group_names(group_names)
        for codename, group_names in getattr(settings, "EXAM_PERMISSION_GROUP_NAMES", {}).items()
    }


def _get_common_exam_group_names():
    return _normalize_group_names(getattr(settings, "COMMON_EXAM_GROUP_NAMES", ()))


def _get_exam_user_group_names(queryset):
    return _normalize_group_names(
        queryset.filter(group__isnull=False).values_list("group__name", flat=True)
    )


def get_exam_group_names(user, exam):
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


def exam_group_names_allow(group_names, permission_codenames):
    permission_group_names = _get_configured_permission_group_names()
    for codename in permission_codenames:
        if group_names & permission_group_names.get(codename, set()):
            return True
    return False
