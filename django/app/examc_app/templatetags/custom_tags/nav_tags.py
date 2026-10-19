from django import template
from django.template import Context
from django.utils.safestring import mark_safe

register = template.Library()

CURRENT_BG = "text-bg-primary"


def _is_current(context, names):
    match = getattr(context.get("request"), "resolver_match", None)
    return bool(match) and match.url_name in names


@register.simple_tag(takes_context=True)
def nav_parent_class(context: Context, *names, css: str = f"active {CURRENT_BG}"):
    """CSS classes for a dropdown toggle when the current page is in its menu."""
    return css if _is_current(context, names) else ""

@register.simple_tag(takes_context=True)
def nav_class(context: Context, *names, css: str = f"active pe-none {CURRENT_BG}"):
    """CSS classes for a link when the current page is one of `names`."""
    return css if _is_current(context, names) else ""


@register.simple_tag(takes_context=True)
def nav_attrs(context: Context, *names):
    """Accessibility attributes for the current page's link."""
    if _is_current(context, names):
        return mark_safe('aria-current="page" aria-disabled="true" tabindex="-1"')
    return ""