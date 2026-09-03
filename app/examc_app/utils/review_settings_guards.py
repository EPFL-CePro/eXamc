from decimal import Decimal, InvalidOperation

from examc_app.models import (
    PageMarkers,
    PagesGroup,
    PagesGroupComment,
    PagesGroupGradingSchemeCheckedBox,
    PagesGroupStudentReportNote,
)


IMMUTABLE_PAGES_GROUP_FIELDS = ("group_name", "nb_pages", "use_grading_scheme")


def decimal_value_changed(current_value, new_raw_value) -> bool:
    if new_raw_value is None:
        return False
    try:
        new_value = Decimal(str(new_raw_value))
    except (InvalidOperation, TypeError, ValueError):
        return True
    return Decimal(current_value) != new_value


def pages_group_has_marker_activity(pages_group: PagesGroup) -> bool:
    return (
        PageMarkers.objects
        .filter(pages_group=pages_group)
        .exclude(copie_no="CORR-BOX")
        .exclude(markers__isnull=True)
        .exclude(markers="")
        .exists()
    )


def pages_group_has_review_activity(pages_group: PagesGroup) -> bool:
    return any((
        pages_group_has_marker_activity(pages_group),
        PagesGroupComment.objects.filter(pages_group=pages_group).exists(),
        PagesGroupGradingSchemeCheckedBox.objects.filter(pages_group=pages_group).exists(),
        PagesGroupStudentReportNote.objects.filter(pages_group=pages_group).exists(),
    ))


def exam_has_review_activity(exam) -> bool:
    pages_groups = PagesGroup.objects.filter(exam=exam)
    return any(pages_group_has_review_activity(group) for group in pages_groups)


def pages_group_settings_changed(existing_group, updated_group) -> bool:
    return any(
        getattr(existing_group, field_name) != getattr(updated_group, field_name)
        for field_name in IMMUTABLE_PAGES_GROUP_FIELDS
    )


def pages_group_name_available(exam, group_name: str, exclude_pages_group_id=None) -> bool:
    queryset = PagesGroup.objects.filter(exam=exam, group_name=group_name)
    if exclude_pages_group_id is not None:
        queryset = queryset.exclude(pk=exclude_pages_group_id)
    return not queryset.exists()


def grading_scheme_has_usage(grading_scheme) -> bool:
    return PagesGroupGradingSchemeCheckedBox.objects.filter(
        gradingSchemeCheckBox__questionGradingScheme=grading_scheme
    ).exists()


def grading_scheme_checkbox_has_usage(grading_scheme_checkbox) -> bool:
    return PagesGroupGradingSchemeCheckedBox.objects.filter(
        gradingSchemeCheckBox=grading_scheme_checkbox
    ).exists()
