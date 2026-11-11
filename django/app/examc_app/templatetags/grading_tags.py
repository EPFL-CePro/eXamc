import json
import os

from django import template
from shapely import Polygon

from examc_app.exceptions import UserFacingError
from examc_app.models import PageMarkers, PagesGroup
from examc_app.services.exam.paths import get_exam_scans_dir
from examc_app.utils.review_functions import get_graded_copies

register = template.Library()



@register.filter
def get_pages_group_graded_count_txt(pages_group_id, user_id=None):
    """
    Grading progress of a pages group, from the number of copies graded and the copies scanned.

    :param user_id: 0 for everyone as "graded / copies" text; a user's id for their progress in percent;
        None for everyone's progress in percent.
    """
    user_id = int(user_id) if user_id not in (None, "") else None  # template arguments can be strings
    as_text = user_id == 0
    for_user = user_id if user_id else None  # 0 and None both mean everyone

    pages_group = PagesGroup.objects.filter(pk=pages_group_id).select_related("exam").first()
    if pages_group is None:
        return "0 / 0" if as_text else 0

    count_graded = len(get_graded_copies(pages_group, for_user))

    try:
        scans_path = get_exam_scans_dir(pages_group.exam)
    except UserFacingError:
        scans_path = None
    # One folder per copy; "0000" holds the scans not matched to a copy
    count_copies = sum(
        1 for entry in os.scandir(scans_path) if entry.is_dir() and entry.name != "0000"
    ) if scans_path and os.path.isdir(scans_path) else 0

    if as_text:
        return f"{count_graded} / {count_copies}"
    if count_copies == 0:
        return 0
    return min(100, round(100 * count_graded / count_copies))


@register.filter
def marker_intersect(marker_info, marker_json):
    pages_group = PagesGroup.objects.get(pk=marker_info[0])
    marker_corrector_box = PageMarkers.objects.filter(exam=pages_group.exam, pages_group=pages_group, copie_no='CORR-BOX').first()
    if marker_corrector_box:
        corr_marker = json.loads(marker_corrector_box.markers)[0]
        left = corr_marker['left']
        top = corr_marker['top']
        width = corr_marker['width']
        height = corr_marker['height']
        a = (left, top)
        b = (left + width, top)
        c = (left + width, top + height)
        d = (left, top + height)
        corr_box_coords = [a, b, c, d]

        _marker = json.loads(marker_json)
        left = corr_marker['left']
        top = corr_marker['top']
        width = corr_marker['width']
        height = corr_marker['height']
        a = (left, top)
        b = (left + width, top)
        c = (left + width, top + height)
        d = (left, top + height)
        marker_coords = [a, b, c, d]

        corr_box_polygon = Polygon(corr_box_coords)
        marker_polygon = Polygon(marker_coords)

        if marker_polygon.intersects(corr_box_polygon):
            return True

    return False