import logging
from typing import Literal

from django import template
from django.db.models import FloatField, Sum
from django.db.models.functions import Cast

from examc_app.models import (
    AnswerStatistic,
    ComVsIndStatistic,
    ScaleDistribution,
    ScaleStatistic,
    Student,
)

register = template.Library()
logger = logging.getLogger(__name__)


# Scale statistics

@register.filter
def get_scale_stats(exam_pk: int, scale_name):
    return ScaleStatistic.objects.get(exam__pk=exam_pk, scale__name=scale_name)


@register.filter
def filter_scales_stats_by_scale(scales_stats, scale_name):
    return scales_stats.filter(scale__name=scale_name)


@register.filter
def get_sections_scaleStats_by_examScale(exam, scale):
    return (
        ScaleStatistic.objects.filter(exam=exam, scale=scale)
        .exclude(section__isnull=True)
        .exclude(section__exact='')
        .exclude(section__exact='GLOBAL')
        .order_by('scale__pk')
    )


# Sections

@register.filter
def get_section_students_count(exam, section):
    print(exam)
    stud_count = Student.objects.filter(exam=exam, section=section).count()
    print(stud_count)
    return stud_count


@register.filter
def get_sections_by_overall_exam(exam):
    return (
        Student.objects.filter(present=True, exam__in=exam.common_exams.all())
        .order_by().values('section').distinct().order_by('section')
    )


# Common vs individual

@register.filter
def get_teachers_comVsInd_scaleStats_by_overall_examScale(overall_exam, scale):
    return ComVsIndStatistic.objects.filter(
        exam__in=overall_exam.common_exams.all(), scale=scale, section=''
    ).order_by('exam__code')


@register.filter
def get_sections_comVsInd_scaleStats_by_overall_examScale(overall_exam, scale):
    return (
        ComVsIndStatistic.objects.filter(exam=overall_exam, scale=scale)
        .exclude(section__isnull=True)
        .exclude(section__exact='')
        .order_by('section')
    )


# Questions

@register.filter
def get_open_question_stats_by_quarter(question):
    quarter_list = []
    quarter_points = question.max_points / 4

    for i in range(1, 5):
        logger.info(quarter_points * i)
        if i == 1:
            students_count = sum(AnswerStatistic.objects.values_list('quantity', flat=True).annotate(answer_float=Cast('answer', FloatField())).filter(question=question, answer_float__lte=quarter_points))
        else:
            students_count = sum(AnswerStatistic.objects.values_list('quantity', flat=True).annotate(answer_float=Cast('answer', FloatField())).filter(question=question, answer_float__gt=float(quarter_points * (i - 1)) + 0.00001, answer_float__lte=quarter_points * i))
        quarter_list.append([i, float(quarter_points * i), students_count])

    return quarter_list


# Achievement

def _get_achievement_by_scale_stat(
    scale_stat: ScaleStatistic,
    variant: Literal["positive", "negative"],
) -> int | str | None:
    distributions = ScaleDistribution.objects.filter(scale_statistic=scale_stat)

    grade_filter: dict[str, int] = (
        {"grade__gte": 4} if variant == "positive" else {"grade__lte": 3}
    )
    count: int | None = distributions.filter(**grade_filter).aggregate(
        total=Sum("quantity")
    )["total"]

    if not count:  # None or 0, returned unchanged as before
        return count

    total: int | None
    if scale_stat.section == "global":
        total = scale_stat.exam.present_students
    else:
        total = distributions.aggregate(total=Sum("quantity"))["total"]

    if not total:  # avoid dividing by zero / None
        return str(count)

    percent = round(100 * count / total, 2)
    return f"{count} ({percent}%)"


@register.filter
def get_achievement_by_scalestat(scale_stat: ScaleStatistic):
    return _get_achievement_by_scale_stat(scale_stat, "positive")


@register.filter
def get_nonachievement_by_scalestat(scale_stat: ScaleStatistic):
    return _get_achievement_by_scale_stat(scale_stat, "negative")