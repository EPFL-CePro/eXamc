import math
from typing import Any

from examc_app.models import Exam, PagesGroupGradingSchemeCheckedBox
from examc_app.utils.amc_db_queries.capture import AmcCaptureDbManager
from examc_app.utils.amc_db_queries.layout import AmcLayoutDbManager
from examc_app.utils.amc_db_queries.scoring import AmcScoringDbManager
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.review_functions import get_question_points


def get_amc_question_layout_and_marks(exam : Exam, copy_nr, pages_group ) -> dict[str, Any]:
    amc_project_path = get_amc_project_path(exam, True)
    amc_data_path = f"{amc_project_path}/data/"

    with AmcLayoutDbManager(amc_data_path=amc_data_path) as amc_layout_db_manager:
        question_page = amc_layout_db_manager.select_copy_question_page(
            copy_nr, pages_group.group_name
        )

    with AmcScoringDbManager(amc_data_path=amc_data_path) as amc_scoring_db_manager:
        max_points = float(
            amc_scoring_db_manager.get_question_max_points(pages_group.group_name, None) or 0
        )

    with AmcCaptureDbManager(amc_data_path=amc_data_path) as amc_capture_db_manager:
        amc_corr_boxes = amc_capture_db_manager.select_marks_positions(
            int(copy_nr), question_page
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