from typing import Any, TypedDict

from examc_app.models import Exam
from examc_app.utils.results_statistics_functions import get_common_list


class ViewTab(TypedDict):
    key: str
    label: str


class ViewContext:
    exam: Exam
    curr_exam: Exam
    user_id: int | None
    user_allowed: bool
    nav_url: str | None

    tabs: list[ViewTab] | None
    curr_tab: str | None

    def __init__(
        self,
        base_dict: dict[str, Any] | None = None,
        exam_pk: int | None = None,
        user_id: int | None = None,
        user_allowed: bool = False,
        nav_url: str | None = None,
        tabs: list[ViewTab] | None = None,
        curr_tab: str | None = None,
    ):
        if base_dict is not None:
            self.update(**base_dict)

        self.set_exam(exam_pk)
        self.set_user_id(user_id)
        self.set_user_allowed(user_allowed)
        self.set_nav_url(nav_url)
        self.set_tabs(tabs)
        self.set_curr_tab(curr_tab)

    def as_dict(self) -> dict[str, Any]:
        """Returns the fully built view context as a dictionary."""
        return {
            key: value
            for key, value in self.__dict__.items()
            if value is not None
        }

    def update(self, **kwargs: Any) -> None:
        """Adds or updates attributes, ignoring None values."""
        self.__dict__.update({
            key: value
            for key, value in kwargs.items()
            if value is not None
        })

    def set_exam(self, exam_pk: int | None) -> None:
        """Sets the current exam and its related exam attributes."""
        if exam_pk is None:
            return

        exam = Exam.objects.get(pk=exam_pk)
        self.curr_exam = exam
        common_list = get_common_list(exam)

        if exam.is_overall():
            self.curr_exam = common_list[1]
            common_list.remove(exam)
        elif common_list:
            self.curr_exam = exam
            self.exam = common_list[0]
            if len(common_list) > 1:
                common_list.remove(exam)

    def set_user_id(self, user_id: int | None = None) -> None:
        """Sets the user ID."""
        if user_id is not None:
            self.user_id = user_id

    def set_user_allowed(self, user_allowed: bool) -> None:
        """Sets whether the user is allowed."""
        self.user_allowed = user_allowed

    def set_nav_url(self, nav_url: str | None = None) -> None:
        """Sets the navigation URL."""
        if nav_url is not None:
            self.nav_url = nav_url

    def set_tabs(self, tabs: list[ViewTab] | None = None) -> None:
        """Manages tabs for display in the view."""
        if tabs is not None:
            self.tabs = tabs

    def set_curr_tab(self, curr_tab: str | None = None) -> None:
        """Sets the current tab."""
        if curr_tab:
            self.curr_tab = curr_tab
