import os
from datetime import datetime

from django import template
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def get_logo_url():
    env = os.getenv("ENV")
    if env == 'prod':
        return static("img/eXamc.svg")
    elif env == "dev":
        return static("img/eXamc-dev.svg")
    else:
        return static("img/eXamc-staging.svg")


@register.filter
def print_timestamp(timestamp):
    try:
        ts = float(timestamp)
    except ValueError:
        return None
    return datetime.fromtimestamp(ts)