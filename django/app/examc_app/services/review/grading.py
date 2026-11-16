import math
from typing import Any

from examc_app.models import (
    Exam,
    PagesGroupGradingSchemeCheckedBox,
    PagesGroupStudentReportNote,
)
from examc_app.utils.amc_db_queries.capture import AmcCaptureDbManager
from examc_app.utils.amc_db_queries.layout import AmcLayoutDbManager, get_amc_copy_nr
from examc_app.utils.amc_db_queries.scoring import AmcScoringDbManager
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.review_functions import (
    get_question_points,
    other_grading_scheme_used,
)


def get_amc_question_layout_and_marks(exam : Exam, copy_nr, pages_group ) -> dict[str, Any]:
    amc_project_path = get_amc_project_path(exam, True)
    amc_data_path = f"{amc_project_path}/data/"
    # copy_nr is a review copy (ID of the QR codes)
    amc_copy_nr = get_amc_copy_nr(amc_data_path, copy_nr)

    with AmcLayoutDbManager(amc_data_path=amc_data_path) as amc_layout_db_manager:
        question_page = amc_layout_db_manager.select_copy_question_page(
            amc_copy_nr, pages_group.group_name
        )

    with AmcScoringDbManager(amc_data_path=amc_data_path) as amc_scoring_db_manager:
        max_points = float(
            amc_scoring_db_manager.get_question_max_points(pages_group.group_name, None) or 0
        )

    with AmcCaptureDbManager(amc_data_path=amc_data_path) as amc_capture_db_manager:
        # Only the boxes of the question of the group: the page may hold other questions
        amc_corr_boxes = amc_capture_db_manager.select_marks_positions(
            amc_copy_nr, question_page, pages_group.group_name
        )

    return {
        "question_page" : question_page,
        "max_points": max_points,
        "amc_corr_boxes" :amc_corr_boxes
    }

def get_review_corr_box_index(grading_scheme, copy_nr):
    if not copy_nr or str(copy_nr) in ('0', 'None', ''):
        return -1

    pages_group = grading_scheme.pages_group
    points = float(get_question_points(grading_scheme, copy_nr))

    if points > grading_scheme.max_points:
        points = float(grading_scheme.max_points)

    if points > 0:
        exam = pages_group.exam
        layout = get_amc_question_layout_and_marks(exam, copy_nr, pages_group)
        max_points = layout["max_points"]
        amc_corr_boxes = layout["amc_corr_boxes"]

        nb_boxes = len(amc_corr_boxes) / 4 - 1
        if nb_boxes <= 0 or max_points <= 0:
            return -1

        points_per_box = max_points / nb_boxes
        return math.floor(points / points_per_box + 0.5)

    zero_checked = PagesGroupGradingSchemeCheckedBox.objects.filter(
        pages_group=pages_group,
        copy_nr=copy_nr,
        gradingSchemeCheckBox__name='ZERO'
    ).exists()
    return 0 if zero_checked else -1


def get_student_report_note(pages_group, copy_nr) -> tuple[str, bool]:
    """
    Return the student's report note for a pages group, and whether notes can be written for this copy.

    Notes are per student, so there is none for copy "0" (the model answer) or without a copy.

    :param pages_group: The pages group the note belongs to.
    :param copy_nr: The copy number.
    :return: (note content, note enabled)
    """
    note_enabled = str(copy_nr) not in ("0", "None", "")
    if not note_enabled:
        return "", False

    note = PagesGroupStudentReportNote.objects.filter(
        pages_group=pages_group,
        copy_nr=copy_nr,
    ).first()
    return (note.content if note else ""), True


def get_shown_grading_scheme(grading_scheme, copy_nr):
    """
    A copy already graded with another scheme stays on it. Otherwise the requested scheme is the one shown.
    """
    used_grading_scheme = other_grading_scheme_used(grading_scheme, copy_nr)
    if used_grading_scheme and get_question_points(used_grading_scheme, copy_nr) > 0:
        return used_grading_scheme
    return grading_scheme
