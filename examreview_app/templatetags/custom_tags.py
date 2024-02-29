from django import template
from django.utils.safestring import mark_safe



register = template.Library()

@register.filter
def get_number_of_pages(group_name,scan_pathes_list):
    return len(scan_pathes_list[group_name])
