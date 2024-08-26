import operator
from datetime import datetime

from django import template
from django.contrib.auth.models import User
from django.db.models import FloatField, Sum
from django.db.models.functions import Cast

from examc_app.models import ScaleDistribution, ComVsIndStatistic, Exam
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
def is_reviewer(user,exam):
    auth_user = User.objects.get(username=user.username)

    if auth_user in exam.users.all() or auth_user.is_superuser:
        return False
    else:
        for exam_reviewer in exam.reviewers.all():
            if auth_user == exam_reviewer.user:
                return True

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

# @register.filter
# def get_students_results_tbody(exam,user):
#     inner_html = ''
#     for student in exam.students.all():
#         inner_html += ('<tr>'
#                       '<td>{{ student.copie_no }}</td>'
#                       '<td>{{ student.sciper }}</td>'
#                       '<td>{{ student.name }}</td>'
#                       '<td><a hidden>'+str(student.present)+'</a>'
#                       '<div class="btn-group btn-group-toggle" data-toggle="buttons" style="margin-left:-20px;">')
#
#         if student.present:
#             inner_html += ('<label class="btn btn-light btn-sm active" style="background-color: transparent;">'
#                           '<input type="radio" name="options" id="present-'+str(student.id)+'-1" checked')
#             if not user.is_staff:
#                 inner_html += ' disabled'
#
#             inner_html += ('><i class="fa-solid fa-circle-check fa-2xl"></i>'
#                           '</label>'
#                           '<label class="btn btn-light btn-sm" style="background-color: transparent;">'
#                           '<input type="radio" name="options" id="present-{{student.pk}}-0"')
#             if not user.is_staff :
#                 inner_html += ' disabled'
#             inner_html += ('><i class="fa-solid fa-circle-xmark fa-2xl" style="color:lightgray;"></i>'
#                           '</label>')
#         else:
#             inner_html += ('<label class="btn btn-light btn-sm" style="background-color: transparent;">'
#                            '<input type="radio" name="options" id="present-' + str(student.id) + '-1" checked')
#             if not user.is_staff:
#                 inner_html += ' disabled'
#
#             inner_html += ('><i class="fa-solid fa-circle-check fa-2xl"></i>'
#                            '</label>'
#                            '<label class="btn btn-light btn-sm" style="background-color: transparent;">'
#                            '<input type="radio" name="options" id="present-{{student.pk}}-0"')
#             if not user.is_staff:
#                 inner_html += ' disabled'
#             inner_html += ('><i class="fa-solid fa-circle-xmark fa-2xl" style="color:lightgray;"></i>'
#                            '</label>')
#
#         inner_html += ('</div>'
#                       '</td>'
#                       '<td>'+str(student.points)+'</td>')
#
#         if student.scaleGrades:
#             scale_grades = sorted(student.scaleGrades.all(), key=operator.attrgetter('scale.name'))
#             for scale_grade in scale_grades:
#                 inner_html += '<td>'+str(scale_grade.grade)+'</td>'
#         else:
#             scales = student.exam.scales.all()
#             for scale in scales:
#                 inner_html += '<td>abs</td>'
#
#         inner_html += '</tr>'
#
#     return inner_html