from django import template
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.utils.safestring import SafeString

register = template.Library()


@register.filter
def get_user_all_infos(user: int | User | None, output: str = "text") -> str | SafeString:
    """
    The user's full name, username and email.

    Usage:
      {{ user|get_user_all_infos }}         → Jane Doe (jdoe) - jane.doe@example.com
      {{ user|get_user_all_infos:"html" }}  → the same, with the username in <code>

    The name and the email are left out when empty. A user id is accepted too, but costs one query per call.
    """
    if isinstance(user, int):
        user = User.objects.filter(pk=user).first()
    if user is None:
        return "Unknown user"

    full_name: str = user.get_full_name()
    email: str = user.email

    if output == "html":
        return format_html(
            "{}(<code>{}</code>){}",
            format_html("{} ", full_name) if full_name else "",
            user.username,
            format_html(" - <a href='mailto:{}'>{}</a>", email, email) if email else "",
        )

    text: str = f"{full_name} ({user.username})" if full_name else user.username
    return f"{text} - {email}" if email else text