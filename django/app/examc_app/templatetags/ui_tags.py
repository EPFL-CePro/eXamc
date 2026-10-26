import os
from collections.abc import Collection
from typing import NotRequired, TypedDict, cast

from django import template
from django.http import HttpRequest
from django.template import Context
from django.template.base import (
    FilterExpression,
    Node,
    NodeList,
    Parser,
    Token,
    token_kwargs,
)
from django.template.exceptions import TemplateSyntaxError
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import SafeString

register = template.Library()


@register.simple_tag
def get_logo_url() -> str:
    env: str | None = os.getenv("ENV")
    if env == "prod":
        return static("img/eXamc.svg")
    if env == "dev":
        return static("img/eXamc-dev.svg")
    return static("img/eXamc-staging.svg")


# ---------------------------------------------------------------------------
# Pill tabs: {% pill_header %} with its {% pill_tab %}s, then a {% pill_pane %} per tab
# ---------------------------------------------------------------------------

TAB_PARAM = "tab"

# Where the tabs of the {% pill_header %} being rendered register themselves (a stack, for nested headers)
_TABS_KEY = "pill_header_tabs"


class Tab(TypedDict):
    key: str
    label: str
    icon: NotRequired[str]
    disabled: NotRequired[bool]
    tooltip: NotRequired[str]

def _tabs_stack(context: Context) -> list[list[Tab]]:
    """
    The tabs of the {% pill_header %}s being rendered, innermost last (a stack, for nested headers).
    The render context is typed for Django's own values: this key is ours, and only ever holds this stack.
    """
    return cast("list[list[Tab]]", cast(object, context.render_context.setdefault(_TABS_KEY, [])))

def _parse_arguments(
    parser: Parser,
    token: Token,
    *,
    positional: int = 0,
    allowed: Collection[str] = (),
    required: Collection[str] = (),
) -> tuple[str, list[FilterExpression], dict[str, FilterExpression]]:
    """
    Parses a tag's arguments: exactly `positional` positional arguments, then keyword arguments only.

    :return: The tag's name, its positional arguments, and its keyword arguments.
    :raises TemplateSyntaxError: On missing positional arguments, positional arguments after keywords,
        or unknown or missing keyword arguments.
    """
    tag_name, *bits = token.split_contents()

    if len(bits) < positional:
        raise TemplateSyntaxError(f"'{tag_name}' requires {positional} positional argument(s).")
    args = [parser.compile_filter(bit) for bit in bits[:positional]]

    remaining = bits[positional:]
    kwargs = token_kwargs(remaining, parser)
    if remaining:
        raise TemplateSyntaxError(f"'{tag_name}' only accepts keyword arguments here, got {remaining[0]!r}.")

    unknown = kwargs.keys() - set(allowed)
    if unknown:
        raise TemplateSyntaxError(f"'{tag_name}' got unexpected keyword arguments: {', '.join(sorted(unknown))}.")
    missing = set(required) - kwargs.keys()
    if missing:
        raise TemplateSyntaxError(f"'{tag_name}' requires the keyword arguments: {', '.join(sorted(missing))}.")

    return tag_name, args, kwargs


def _resolve(kwargs: dict[str, FilterExpression], name: str, context: Context, default: object = None) -> object:
    """A keyword argument's value, or `default` when it isn't given."""
    return kwargs[name].resolve(context) if name in kwargs else default


class PillHeaderNode(Node):
    def __init__(self, nodelist: NodeList, kwargs: dict[str, FilterExpression]) -> None:
        self.nodelist = nodelist
        self.kwargs = kwargs

    def render(self, context: Context) -> SafeString:
        prefix = str(_resolve(self.kwargs, "prefix", context))

        # The tabs register themselves while the block renders; the rest of the block is the content
        stack = _tabs_stack(context)
        stack.append([])
        try:
            content = self.nodelist.render(context)
        finally:
            tabs = stack.pop()

        # The selected tab: ?tab= if valid, else `active` if valid, else the first one; never a disabled one
        enabled = [tab["key"] for tab in tabs if not tab.get("disabled")]
        request: HttpRequest | None = context.get("request")
        requested = request.GET.get(TAB_PARAM) if request is not None else None
        active = _resolve(self.kwargs, "active", context)
        selected = next((key for key in (requested, active) if key in enabled), enabled[0] if enabled else None)

        # For the {% pill_pane %}s that follow
        context[f"{prefix}_active_tab"] = selected

        component = context.template.engine.get_template("components/pill_header.html")
        with context.push(
            title=_resolve(self.kwargs, "title", context),
            icon=_resolve(self.kwargs, "icon", context, ""),
            prefix=prefix,
            active=selected,
            tabs=tabs,
            content=content,
        ):
            return component.render(context)


@register.tag
def pill_header(parser: Parser, token: Token) -> PillHeaderNode:
    """
    Usage:
      {% pill_header title="Preparation" prefix="preparation" icon="fas fa-edit" active="exam" %}
          {% pill_tab "exam" label="Exam" icon="fas fa-book-open" %}
          {% pill_tab "students" %}
          ... anything else, shown after the tabs ...
      {% endpill_header %}
    The selected tab is ?tab= if valid, else `active` if valid, else the first tab; never a disabled one.
    Sets `<prefix>_active_tab` in the page context, for the {% pill_pane %}s that follow.
    """
    tag_name, _, kwargs = _parse_arguments(
        parser, token, allowed={"title", "prefix", "icon", "active"}, required={"title", "prefix"},
    )
    nodelist = parser.parse((f"end{tag_name}",))
    parser.delete_first_token()
    return PillHeaderNode(nodelist, kwargs)


class PillTabNode(Node):
    def __init__(self, key: FilterExpression, kwargs: dict[str, FilterExpression]) -> None:
        self.key = key
        self.kwargs = kwargs

    def render(self, context: Context) -> str:
        stack = _tabs_stack(context)
        if not stack:
            raise TemplateSyntaxError("{% pill_tab %} must be inside a {% pill_header %} block.")

        key = str(self.key.resolve(context))
        tab: Tab = {"key": key, "label": str(_resolve(self.kwargs, "label", context, "")) or key.title()}
        if icon := str(_resolve(self.kwargs, "icon", context, "")):
            tab["icon"] = icon
        if tooltip := str(_resolve(self.kwargs, "tooltip", context, "")):
            tab["tooltip"] = tooltip
        if _resolve(self.kwargs, "disabled", context, False):
            tab["disabled"] = True

        # Rendered by the header, with the other tabs: nothing here
        stack[-1].append(tab)
        return ""


@register.tag
def pill_tab(parser: Parser, token: Token) -> PillTabNode:
    """
    Usage, inside {% pill_header %}:
      {% pill_tab "grading" label="Grading" icon="fas fa-check" disabled=grading_locked tooltip="Locked." %}
    The first argument is the tab's key; `label` defaults to the title-cased key.
    `icon`, `disabled` and `tooltip` are optional; a disabled tab is never selected.
    """
    _, (key,), kwargs = _parse_arguments(
        parser, token, positional=1, allowed={"label", "icon", "disabled", "tooltip"},
    )
    return PillTabNode(key, kwargs)


class PillPaneNode(Node):
    def __init__(self, nodelist: NodeList, tab: FilterExpression, kwargs: dict[str, FilterExpression]) -> None:
        self.nodelist = nodelist
        self.tab = tab
        self.kwargs = kwargs

    def render(self, context: Context) -> SafeString:
        value = self.tab.resolve(context)
        key = str(value["key"] if isinstance(value, dict) else value)
        prefix = str(_resolve(self.kwargs, "prefix", context))

        content = self.nodelist.render(context)

        return format_html(
            '<div class="tab-pane fade{}" id="pills-{}-{}" role="tabpanel" aria-labelledby="{}-{}-tab" tabindex="0">{}</div>',
            " show active" if context.get(f"{prefix}_active_tab") == key else "",
            prefix, key, prefix, key,
            content,
        )


@register.tag
def pill_pane(parser: Parser, token: Token) -> PillPaneNode:
    """
    Usage:
      {% pill_pane "grading" prefix="preparation" disabled=is_locked tooltip="Locked: review data already exists." %}
          ...
      {% endpill_pane %}
    The first argument is the tab's key, or a Tab dict.
    `disabled` (optional) makes the content visible but unusable; `tooltip` (optional) explains why.
    Must come after the matching {% pill_header %}, which sets `<prefix>_active_tab`.
    """
    tag_name, (tab,), kwargs = _parse_arguments(
        parser, token, positional=1, allowed={"prefix"}, required={"prefix"},
    )
    nodelist = parser.parse((f"end{tag_name}",))
    parser.delete_first_token()
    return PillPaneNode(nodelist, tab, kwargs)



# ---------------------------------------------------------------------------
# Alerts: {% alert "info" %}...{% endalert %}
# ---------------------------------------------------------------------------

# The kinds of alerts, with their default icon
ALERT_ICONS: dict[str, str] = {
    "info": "fa-solid fa-circle-info",
    "success": "fa-solid fa-circle-check",
    "warning": "fa-solid fa-triangle-exclamation",
    "danger": "fa-solid fa-circle-exclamation",
    "secondary": "",
    "light": "",
    "dark": "",
}

# Kinds that need the user's attention: announced by screen readers as soon as they appear (role="alert")
_URGENT_KINDS = {"warning", "danger"}


class AlertNode(Node):
    def __init__(self, nodelist: NodeList, kind: FilterExpression, kwargs: dict[str, FilterExpression]) -> None:
        self.nodelist = nodelist
        self.kind = kind
        self.kwargs = kwargs

    def render(self, context: Context) -> SafeString:
        kind = str(self.kind.resolve(context))
        if kind not in ALERT_ICONS:
            raise TemplateSyntaxError(f"Unknown alert kind {kind!r}: use one of {', '.join(ALERT_ICONS)}.")

        # icon="..." replaces the kind's icon, icon=False removes it
        icon = _resolve(self.kwargs, "icon", context, ALERT_ICONS[kind])
        title = str(_resolve(self.kwargs, "title", context, ""))
        dismissible = bool(_resolve(self.kwargs, "dismissible", context, False))

        classes = ["alert", f"alert-{kind}", str(_resolve(self.kwargs, "class", context, ""))]
        if dismissible:
            classes += ["alert-dismissible", "fade", "show"]

        attributes = format_html(
            ' class="{}"{}{}{}{}',
            " ".join(filter(None, classes)),
            format_html(' id="{}"', _resolve(self.kwargs, "id", context)) if "id" in self.kwargs else "",
            SafeString(' role="alert"') if kind in _URGENT_KINDS else "",
            SafeString(' style="max-width: fit-content"') if _resolve(self.kwargs, "fit", context, False) else "",
            SafeString(" hidden") if _resolve(self.kwargs, "hidden", context, False) else "",
        )

        return format_html(
            "<div{}>{}{}{}{}</div>",
            attributes,
            format_html('<h6 class="alert-heading">{}</h6>', title) if title else "",
            format_html('<i class="{} me-1" aria-hidden="true"></i>', icon) if icon and not title else "",
            self.nodelist.render(context),
            SafeString('<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>')
            if dismissible else "",
        )


@register.tag
def alert(parser: Parser, token: Token) -> AlertNode:
    """
    Usage:
      {% alert "warning" title="Before generating" dismissible=True fit=True %}
          ... any content, links with class="alert-link" ...
      {% endalert %}
    The first argument is the kind: info, success, warning, danger (with an icon), or secondary, light, dark.
    Optional: `title` (a heading, instead of the icon), `icon` (other Font Awesome classes, or False for none),
    `dismissible` (a close button), `fit` (as wide as its content), `id`, `class` (more classes), `hidden`.
    Warnings and errors have role="alert", so screen readers announce them as soon as they appear.
    """
    tag_name, (kind,), kwargs = _parse_arguments(
        parser, token, positional=1,
        allowed={"title", "icon", "dismissible", "fit", "id", "class", "hidden"},
    )
    nodelist = parser.parse((f"end{tag_name}",))
    parser.delete_first_token()
    return AlertNode(nodelist, kind, kwargs)