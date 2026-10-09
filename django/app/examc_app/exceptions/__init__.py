import logging

from django.template import engines
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


class UserFacingError(Exception):
    """An error whose title and message can safely be shown to the user instead of a 500 page."""

    title: str = "Something went wrong"

    #: A Django template rendered with `context`. It may contain HTML and template tags,
    #: but must only ever be written in code: put dynamic values in `context`, never in this string.
    message: str = "Please try again or contact support."

    action_label: str | None = None
    action_url: str | None = None
    status_code: int = 400
    log_level: int = logging.WARNING

    def __init__(
            self,
            log_message: str = "",
            *,
            context: dict | None = None,
            title: str | None = None,
            message: str | None = None,
            action_label: str | None = None,
            action_url: str | None = None,
            status_code: int | None = None,
            log_level: int | None = None,
    ):
        """
        :param log_message: Technical details for the logs only (paths, ids...). Never shown to the user.
        :param context: Variables available in the message template, e.g. {"exam": exam}.
        Other parameters override the class defaults for this instance.
        """
        self.context = context or {}

        overrides = {
            "title": title,
            "message": message,
            "action_label": action_label,
            "action_url": action_url,
            "status_code": status_code,
            "log_level": log_level,
        }
        for name, value in overrides.items():
            if value is not None:
                setattr(self, name, value)

        super().__init__(log_message or f"{self.title} | {self.message}")

    def render_message(self) -> str:
        """The message as HTML. Falls back to the default message if the template can't be rendered."""
        try:
            return engines["django"].from_string(self.message).render(self.context)
        except Exception:
            logger.exception("Could not render the message of %s", type(self).__name__)
            return UserFacingError.message

    def to_dict(self) -> dict[str, str | None]:
        """What the user sees: used for JSON responses and the error modal."""
        message_html = self.render_message()
        return {
            "title": self.title,
            "detail": strip_tags(message_html),  # plain text, for API clients
            "detail_html": message_html,         # for the modal
            "action_label": self.action_label,
            "action_url": self.action_url,
        }


def log_user_facing_error(exception: UserFacingError, method: str, path: str) -> None:
    logger.log(
        exception.log_level,
        "%s on %s %s: %s",
        type(exception).__name__, method, path, exception,
        exc_info=exception,
    )