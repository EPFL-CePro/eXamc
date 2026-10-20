from typing import TypedDict

from examc_app.models import Exam
from examc_app.utils.results_statistics_functions import get_common_list


class BaseViewContext(TypedDict):
    exam: Exam
    exam_selected: Exam
    user_id: int

def get_base_view_context(exam_pk: int, user_id: int) -> dict:
    """Returns a dictionary containing the exam context for the given exam and user."""
    exam = Exam.objects.get(pk=exam_pk)
    curr_exam = exam
    common_list = get_common_list(exam)

    if exam.is_overall():
        curr_exam = common_list[1]
        common_list.remove(exam)
    elif common_list:
        curr_exam = exam
        exam = common_list[0]
        if len(common_list) > 1:
            common_list.remove(exam)
            
    return dict(BaseViewContext(exam=exam, exam_selected=curr_exam, user_id=user_id))
