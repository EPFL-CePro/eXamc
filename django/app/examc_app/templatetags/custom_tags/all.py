from django import template

from . import (
    collection_filters,
    exam_tags,
    grading_tags,
    math_filters,
    nav_tags,
    permission_tags,
    stats_tags,
    ui_tags,
)

register = template.Library()

for module in (
    collection_filters,
    exam_tags,
    grading_tags,
    math_filters,
    nav_tags,
    permission_tags,
    stats_tags,
    ui_tags,
):
    register.filters.update(module.register.filters)
    register.tags.update(module.register.tags)