import json
import operator
import os
from datetime import datetime

from django import template
from django.contrib.auth.models import User
from django.db.models import FloatField, Sum
from django.db.models.functions import Cast
from matplotlib.sphinxext.plot_directive import exception_template
from shapely import Polygon

from django.conf import settings
from examc_app.models import ScaleDistribution, ComVsIndStatistic, Exam, PagesGroup, PageMarkers, ExamUser, ReviewLock
from examc_app.models import ScaleStatistic, Student, AnswerStatistic, logger

register = template.Library()

@register.filter
def get_number_of_pages(group_name,scan_pathes_list):
    return len(scan_pathes_list[group_name])

@register.filter
def print_timestamp(timestamp):
    try:
        ts = float(timestamp)
    except ValueError:
        return None
    return datetime.fromtimestamp(ts)

@register.filter
def more_arg(_1, _2):
    return _1, _2

@register.filter
def is_allowed(_user_exam,option):
    user, exam = _user_exam
    auth_user = User.objects.get(pk=user.pk)
    if auth_user.is_superuser:
        return True

    group_ids_allowed = []

    if option == 'preparation':
        group_ids_allowed = [2,4]
    elif option == 'creation':
        if user.groups.filter(pk__in=[1,2,4,5]).exists():
            return True
        else:
            return False
    elif option == 'amc':
        group_ids_allowed = [2,4]
    elif option =='res_and_stats':
        group_ids_allowed = [2,4]
    elif option =='review':
        group_ids_allowed = [2,4]

    try:
        exam_user = ExamUser.objects.get(exam=exam, user=auth_user, group__in=group_ids_allowed)
        return True
    except ExamUser.DoesNotExist:
        return False

@register.filter
def is_admin(user):
    auth_user = User.objects.get(username=user.username)

    if auth_user.is_superuser:
        return True

@register.filter
def get_scale_stats(exam_pk, scale_name):
    result = ScaleStatistic.objects.get(exam__pk=exam_pk, scale__name=scale_name)
    return result

@register.filter
def filter_scales_stats_by_scale(scales_stats,scale_name):
    result = scales_stats.filter(scale__name=scale_name)
    return result

@register.filter
def get_item_pos(qs,item):
    return list(qs).index(item)

@register.filter
def substract(value, arg):
    return value - arg

@register.filter
def add(value, arg):
    return value + arg

@register.filter
def divide(value, arg):
    return value / arg

@register.filter
def multiply(value, arg):
    return value * arg

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def get_sections_scaleStats_by_examScale(exam,scale):
    results = ScaleStatistic.objects.filter(exam=exam, scale=scale).exclude(section__isnull=True).exclude(section__exact='').exclude(section__exact='GLOBAL').order_by('scale__pk')
    return results
@register.filter
def get_section_students_count(exam,section):
    print(exam)
    stud_count = Student.objects.filter(exam=exam, section=section).count()
    print(stud_count)
    return stud_count

@register.filter
def get_sections_by_overall_exam(exam):
    return Student.objects.filter(present=True,exam__in=exam.common_exams.all()).order_by().values('section').distinct().order_by('section')

@register.filter
def get_teachers_comVsInd_scaleStats_by_overall_examScale(overall_exam,scale):
    return ComVsIndStatistic.objects.filter(exam__in=overall_exam.common_exams.all(), scale=scale, section='').order_by('exam__code')

@register.filter
def get_sections_comVsInd_scaleStats_by_overall_examScale(overall_exam,scale):
    return ComVsIndStatistic.objects.filter(exam=overall_exam, scale=scale).exclude(section__isnull=True).exclude(section__exact='').order_by('section')

@register.filter
def get_open_question_stats_by_quarter(question):
    quarter_list = []
    quarter_points = question.max_points / 4

    for i in range (1,5):
        logger.info(quarter_points*i)
        if i == 1:
            students_count = sum(AnswerStatistic.objects.values_list('quantity',flat=True).annotate(answer_float=Cast('answer', FloatField())).filter(question=question,answer_float__lte=quarter_points))
        else:
            students_count = sum(AnswerStatistic.objects.values_list('quantity',flat=True).annotate(answer_float=Cast('answer', FloatField())).filter(question=question,answer_float__gt=float(quarter_points*(i-1))+0.00001,answer_float__lte=quarter_points*i))
        quarter_list.append([i,float(quarter_points*i),students_count])

    return quarter_list

@register.filter
def get_achievement_by_scalestat(scale_stat):
    ach = ScaleDistribution.objects.filter(scale_statistic__id=scale_stat.id,grade__gte=4).values('quantity').aggregate(Sum('quantity')).get('quantity__sum')

    if ach > 0:
      if scale_stat.section == 'global':
          ach = str(ach) + " ( " + str(round(100/scale_stat.exam.present_students*ach,2)) + "% )"
      else:
          tot_stud_section = ScaleDistribution.objects.filter(scale_statistic__id=scale_stat.id).values('quantity').aggregate(Sum('quantity')).get('quantity__sum')
          ach = str(ach) + " ( " + str(round(100/tot_stud_section*ach,2)) + "% )"
    return ach

@register.filter
def get_nonachievement_by_scalestat(scale_stat):
    nonach = ScaleDistribution.objects.filter(scale_statistic__id=scale_stat.id,grade__lt=4).values('quantity').aggregate(Sum('quantity')).get('quantity__sum')
    if nonach > 0:
      if scale_stat.section == 'global':
          nonach = str(nonach) + " ( " + str(round(100/scale_stat.exam.present_students*nonach,2)) + "% )"
      else:
          tot_stud_section = ScaleDistribution.objects.filter(scale_statistic__id=scale_stat.id).values('quantity').aggregate(Sum('quantity')).get('quantity__sum')
          nonach = str(nonach) + " ( " + str(round(100/tot_stud_section*nonach,2)) + "% )"
    return nonach

@register.filter
def divideMult100(value, arg):
    if value <= 0 or arg <= 0:
      return 0
    try:
        return int(value) / int(arg) * 100
    except (ValueError, ZeroDivisionError):
        return 0

@register.filter
def get_frm_by_id(l, i):
    try:
        return l[i]
    except:
        return None

@register.filter
def get_pages_group_graded_count_txt(pages_group_id,user_id=None):
    pages_group = PagesGroup.objects.get(pk=pages_group_id)
    count_graded = 0
    if user_id and user_id != 0:
        count_graded = PageMarkers.objects.filter(pages_group=pages_group, correctorBoxMarked=True,pageMarkers_users__user__id=user_id).count()
    else:
        count_graded = PageMarkers.objects.filter(pages_group=pages_group,correctorBoxMarked=True).count()
    scans_path =  str(settings.SCANS_ROOT) + "/" + str(pages_group.exam.year.code) + "/" + str(pages_group.exam.semester.code) + "/" + pages_group.exam.code+"_"+pages_group.exam.date.strftime("%Y%m%d")
    if os.path.exists(scans_path):
        scans_folders = [x for x in os.listdir(scans_path) if x != '0000']
        count_copies = len(scans_folders)

        if user_id == 0:
            return str(int(count_graded)) + " / " + str(count_copies)
        elif user_id and user_id != 0:
            return int(100/count_copies*count_graded)
        else:
            return int(100/count_copies*count_graded)
    else:
        return 0


@register.filter
def marker_intersect(marker_info, marker_json):
    pages_group = PagesGroup.objects.get(pk=marker_info[0])
    marker_corrector_box = PageMarkers.objects.filter(exam=pages_group.exam, pages_group=pages_group,copie_no='CORR-BOX').first()
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

@register.filter
def get_exam_teachers_short_str(exam_id):
    exam = Exam.objects.get(pk=exam_id)
    teachers_str = ''
    for exam_user in exam.exam_users.all():
        if exam_user.group.id == 2:
            if teachers_str:
                teachers_str += ', '
            teachers_str += exam_user.user.first_name[0]+"."+exam_user.user.last_name

    return teachers_str

@register.filter
def get_sum_questions_points(exam_id):
    exam = Exam.objects.get(pk=exam_id)
    return exam.questions.all().aggregate(Sum('max_points')).get('max_points__sum')