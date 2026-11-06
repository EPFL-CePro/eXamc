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
    Template,
    Token,
    token_kwargs,
)
from django.template.exceptions import TemplateSyntaxError
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import SafeString

register = template.Library()


def _get_template_from_context(context: Context) -> Template:
    context_template = context.template
    if not isinstance(context_template, Template):
        raise TemplateSyntaxError("Template not available in context")

    return context_template


@register.simple_tag
def get_logo_url() -> str:
    env: str | None = os.getenv("ENV")
    if env == "prod":
        return static("img/eXamc.svg")
    if env == "dev":
        return static("img/eXamc-dev.svg")
    return static("img/eXamc-staging.svg")


# ---------------------------------------------------------------------------
# Pill tabs: {% pill_header %} with its {% pill_tab %}s, then a {% tab_pane %} per tab
# ---------------------------------------------------------------------------

TAB_PARAM = "tab"

# Where the tabs of the {% pill_header %} being rendered register themselves (a stack, for nested headers)
_TABS_KEY = "pill_header_tabs"
_TAB_PREFIX_KEY = "_tab_content_prefix"

class Tab(TypedDict):
    key: str
    label: str
    icon: NotRequired[str]
    disabled: NotRequired[bool]
    disabled_tooltip: NotRequired[str]
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

def _resolve_str(kwargs: dict[str, FilterExpression], name: str, context: Context, default: str = "") -> str:
    """A keyword argument's value as a string, or `default` when it isn't given or is empty."""
    value = kwargs[name].resolve(context) if name in kwargs else default
    return str(value) if value not in (None, "") else default


def _resolve_bool(kwargs: dict[str, FilterExpression], name: str, context: Context, default: bool = False) -> bool:
    """A keyword argument's truthiness, or `default` when it isn't given."""
    return bool(kwargs[name].resolve(context)) if name in kwargs else default

class PillHeaderNode(Node):
    def __init__(self, nodelist: NodeList, kwargs: dict[str, FilterExpression]) -> None:
        self.nodelist = nodelist
        self.kwargs = kwargs

    def render(self, context: Context) -> SafeString:
        prefix = _resolve_str(self.kwargs, "prefix", context)

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
        active = _resolve_str(self.kwargs, "active", context)
        selected = next((key for key in (requested, active) if key in enabled), enabled[0] if enabled else None)

        # For the {% tab_pane %}s that follow
        context[f"{prefix}_active_tab"] = selected

        context_template = _get_template_from_context(context)
        component = context_template.engine.get_template("components/pill_header.html")

        with context.push(
            title=_resolve_str(self.kwargs, "title", context),
            icon=_resolve_str(self.kwargs, "icon", context, ""),
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
    Sets `<prefix>_active_tab` in the page context, for the {% tab_pane %}s that follow.
    """
    tag_name, _, kwargs = _parse_arguments(
        parser, token, allowed={"title", "prefix", "icon", "active"}, required={"prefix"},
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
        tab: Tab = {"key": key, "label": _resolve_str(self.kwargs, "label", context, "") or key.title()}
        if icon := _resolve_str(self.kwargs, "icon", context, ""):
            tab["icon"] = icon
        if tooltip := _resolve_str(self.kwargs, "tooltip", context, ""):
            tab["tooltip"] = tooltip
        if disabled_tooltip := _resolve_str(self.kwargs, "disabled_tooltip", context, ""):
            tab["disabled_tooltip"] = disabled_tooltip
        if (_resolve_bool(self.kwargs, "disabled", context, False)
                or not _resolve_bool(self.kwargs, "enabled", context, True)):
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
    `icon`, `disabled`, `disabled_tooltip` and `tooltip` are optional; a disabled tab is never selected.
    `enabled` does the opposite of `disabled`, it's used to simplify templates markup.
    """
    _, (key,), kwargs = _parse_arguments(
        parser, token, positional=1, allowed={"label", "icon", "enabled", "disabled", "tooltip", "disabled_tooltip"},
    )
    return PillTabNode(key, kwargs)

class TabContentNode(Node):
    def __init__(self, nodelist: NodeList, kwargs: dict[str, FilterExpression]) -> None:
        self.nodelist = nodelist
        self.kwargs = kwargs

    def render(self, context: Context) -> SafeString:
        prefix = str(self.kwargs["prefix"].resolve(context))
        div_id = _resolve_str(self.kwargs, "id", context, "") or f"{prefix}-tab-content"
        style = _resolve_str(self.kwargs, "style", context, "")

        # A nested {% tab_content %} pushes its own prefix, and pops it when done
        with context.push({_TAB_PREFIX_KEY: prefix}):
            content = self.nodelist.render(context)

        return format_html(
            '<div class="tab-content" id="{}"{}>{}</div>',
            div_id,
            format_html(' style="{}"', style) if style else "",
            content,
        )


class TabPaneNode(Node):
    def __init__(self, nodelist: NodeList, key: FilterExpression) -> None:
        self.nodelist = nodelist
        self.key = key

    def render(self, context: Context) -> SafeString:
        prefix = context.get(_TAB_PREFIX_KEY)
        if prefix is None:
            raise TemplateSyntaxError("{% tab_pane %} must be inside a {% tab_content %} block.")

        value = self.key.resolve(context)
        key = str(value["key"] if isinstance(value, dict) else value)

        # Set by the {% pill_header %} with the same prefix
        active = context.get(f"{prefix}_active_tab") == key

        return format_html(
            '<div class="tab-pane fade{}" id="pills-{}-{}" role="tabpanel" '
            'aria-labelledby="{}-{}-tab" tabindex="0">{}</div>',
            " show active" if active else "",
            prefix, key, prefix, key,
            self.nodelist.render(context),
        )


@register.tag
def tab_content(parser: Parser, token: Token) -> TabContentNode:
    """
    Usage, after the {% pill_header %} with the same prefix:
      {% tab_content prefix="import" id="example" style="max-width: 20rem" %}
          {% tab_pane "amc-csv" %} ... {% endtab_pane %}
      {% endtab_content %}
    The {% tab_pane %}s inside, at any depth, use this prefix; a nested {% tab_content %} sets its own.
    """
    tag_name, _, kwargs = _parse_arguments(parser, token, allowed={"prefix", "id", "style"}, required={"prefix"})
    nodelist = parser.parse((f"end{tag_name}",))
    parser.delete_first_token()
    return TabContentNode(nodelist, kwargs)


@register.tag
def tab_pane(parser: Parser, token: Token) -> TabPaneNode:
    """
    Usage, inside {% tab_content %}:
      {% tab_pane "amc-csv" %} ... {% endtab_pane %}
    The argument is the key of the matching {% pill_tab %}; the prefix comes from the enclosing {% tab_content %}.
    """
    tag_name, (key,), _ = _parse_arguments(parser, token, positional=1)
    nodelist = parser.parse((f"end{tag_name}",))
    parser.delete_first_token()
    return TabPaneNode(nodelist, key)


# ---------------------------------------------------------------------------
# Titles: {% title "Exam" icon="fas fa-book-open" %}
# ---------------------------------------------------------------------------

class TitleNode(Node):
    def __init__(self, text: FilterExpression, kwargs: dict[str, FilterExpression]) -> None:
        self.text = text
        self.kwargs = kwargs

    def render(self, context: Context) -> str:
        context_template = _get_template_from_context(context)
                
        component = context_template.engine.get_template("components/title.html")
        with context.push(
            title=self.text.resolve(context),
            icon=_resolve_str(self.kwargs, "icon", context),
        ):
            return component.render(context)


@register.tag
def title(parser: Parser, token: Token) -> TitleNode:
    """
    Usage:
      {% title "Import" icon="fas fa-upload" %}
    The first argument is the title's text; `icon` (Font Awesome classes) is optional.
    """
    _, (text,), kwargs = _parse_arguments(parser, token, positional=1, allowed={"icon"})
    return TitleNode(text, kwargs)



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
_ALERT_URGENT_KINDS = {"warning", "danger"}


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
        icon = _resolve_str(self.kwargs, "icon", context, ALERT_ICONS[kind])
        alert_title = _resolve_str(self.kwargs, "title", context, "")
        dismissible = _resolve_bool(self.kwargs, "dismissible", context, False)
        margin = _resolve_bool(self.kwargs, "margin", context, True)

        classes: list[str] = ["alert", f"alert-{kind}", _resolve_str(self.kwargs, "class", context, "")]
        if dismissible:
            classes += ["alert-dismissible", "fade", "show"]

        if not margin:
            classes += ["m-0"]

        # hidden=True hides the alert; visible=False does too (visible defaults to True)
        is_hidden = (
            _resolve_bool(self.kwargs, "hidden", context, False)
            or not _resolve_bool(self.kwargs, "visible", context, True)
        )

        attributes = format_html(
            ' class="{}"{}{}{}{}',
            " ".join(filter(None, classes)),
            format_html(' id="{}"', _resolve_str(self.kwargs, "id", context)) if "id" in self.kwargs else "",
            SafeString(' role="alert"') if kind in _ALERT_URGENT_KINDS else "",
            SafeString(' style="max-width: fit-content"') if _resolve_bool(self.kwargs, "fit", context, False) else "",
            SafeString(" hidden") if is_hidden else "",
        )

        return format_html(
            "<div{}>{}{}{}{}</div>",
            attributes,
            format_html('<h6 class="alert-heading">{}</h6>', alert_title) if alert_title else "",
            format_html('<i class="{} me-1" aria-hidden="true"></i>', icon) if icon and not alert_title else "",
            self.nodelist.render(context),
            SafeString('<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>')
            if dismissible else "",
        )


@register.tag
def alert(parser: Parser, token: Token) -> AlertNode:
    """
    Usage:
      {% alert "warning" title="Before generating" dismissible=True fit=True margin=False %}
          ... any content, links with class="alert-link" ...
      {% endalert %}
    The first argument is the kind: info, success, warning, danger (with an icon), or secondary, light, dark.
    Optional: `title` (a heading, instead of the icon), `icon` (other Font Awesome classes, or False for none),
    `dismissible` (a close button), `fit` (as wide as its content), `id`, `class` (more classes), `hidden`, `margin`.
    `visible` does the opposite of hidden.
    Warnings and errors have role="alert", so screen readers announce them as soon as they appear.
    """
    tag_name, (kind,), kwargs = _parse_arguments(
        parser, token, positional=1,
        allowed={"title", "icon", "dismissible", "fit", "id", "class", "hidden", "visible", "margin"},
    )
    nodelist = parser.parse((f"end{tag_name}",))
    parser.delete_first_token()
    return AlertNode(nodelist, kind, kwargs)