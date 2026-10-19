from django import template

register = template.Library()


@register.filter
def more_arg(_1, _2):
    return _1, _2


@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)


@register.filter
def get_frm_by_id(l, i):
    try:
        return l[i]
    except:
        return None


@register.filter
def get_item_pos(qs, item):
    return list(qs).index(item)


@register.filter
def get_number_of_pages(group_name, scan_pathes_list):
    return len(scan_pathes_list[group_name])
