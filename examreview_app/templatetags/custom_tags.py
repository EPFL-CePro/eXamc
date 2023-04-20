from django import template

import json

register = template.Library()

@register.filter
def get_number_of_pages(group_name,scan_pathes_list):
    return len(scan_pathes_list[group_name])
