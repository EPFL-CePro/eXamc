from django import template

register = template.Library()


@register.filter
def subtract(value, arg):
    return value - arg

@register.filter
def divide(value, arg):
    return value / arg

@register.filter
def multiply(value, arg):
    return value * arg


@register.filter
def divide_mult_100(value, arg):
    if value <= 0 or arg <= 0:
        return 0
    try:
        return int(value) / int(arg) * 100
    except (ValueError, ZeroDivisionError):
        return 0