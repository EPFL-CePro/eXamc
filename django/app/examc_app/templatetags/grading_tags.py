import json
import os

from django import template
from shapely import Polygon

from examc_app.exceptions import UserFacingError
from examc_app.models import PageMarkers, PagesGroup, PagesGroupGradingSchemeCheckedBox
from examc_app.services.exam.paths import get_exam_scans_dir

register = template.Library()


@register.filter
def get_pages_group_graded_count_txt(pages_group_id, user_id=None):
    pages_group = PagesGroup.objects.get(pk=pages_group_id)
    if pages_group.use_grading_scheme:
        graded_qs = PagesGroupGradingSchemeCheckedBox.objects.filter(pages_group=pages_group)
        if user_id and user_id != 0:
            graded_qs = graded_qs.filter(user_id=user_id)
        count_graded = graded_qs.values("copy_nr").distinct().count()
    elif user_id and user_id != 0:
        count_graded = PageMarkers.objects.filter(pages_group=pages_group, correctorBoxMarked=True, pageMarkers_users__user__id=user_id).count()
    else:
        count_graded = PageMarkers.objects.filter(pages_group=pages_group, correctorBoxMarked=True).count()
    try:
        scans_path = get_exam_scans_dir(pages_group.exam)
    except UserFacingError:
        return 0
    if os.path.exists(scans_path):
        scans_folders = [x for x in os.listdir(scans_path) if x != '0000']
        count_copies = len(scans_folders)
        try:
            print("copies: " + str(count_copies))
            print("graded: " + str(count_graded))
            print("100/c*g: " + str(round(int(100 / count_copies * count_graded))))
            if user_id == 0:
                return str(int(count_graded)) + " / " + str(count_copies)
            elif user_id and user_id != 0:
                return round(100 / count_copies * count_graded)
            else:
                return round(100 / count_copies * count_graded)
        except ZeroDivisionError:
            return 0
    else:
        return 0


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

        marker = json.loads(marker_json)
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