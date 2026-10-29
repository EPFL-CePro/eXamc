from typing import Any, TypedDict

from examc_app.models import Exam, PagesGroup


class ViewTab(TypedDict):
    key: str
    label: str


class ViewContext:
    """
    Builds a view's template context.

    Two exams are kept apart:
      - `exam_selected`: the exam the page is about (the one in the URL). The sidebar, permissions and data use it.
      - `exam`: the common exam of its group, or the exam itself when it isn't part of a group.
    Both are set together by `set_exam`, from the opened exam only: never pass the common exam to it.
    """

    task_id: str | None

    exam: Exam | None
    exam_selected: Exam | None

    user_id: int | None
    user_allowed: bool

    nav_url: str | None

    tabs: list[ViewTab] | None
    curr_tab: str | None

    pages_group: PagesGroup | None

    def __init__(
        self,
        base_dict: dict[str, Any] | None = None,

        task_id: str | None = None,

        exam: Exam | None = None,
        exam_pk: int | None = None,

        user_id: int | None = None,
        user_allowed: bool = False,

        nav_url: str | None = None,

        tabs: list[ViewTab] | None = None,
        curr_tab: str | None = None,

        pages_group: PagesGroup | None = None,
    ):
        # Every attribute exists, so reading one that wasn't set gives None instead of an AttributeError
        self.task_id = None
        self.exam = None
        self.exam_selected = None
        self.user_id = None
        self.user_allowed = False
        self.nav_url = None
        self.tabs = None
        self.curr_tab = None
        self.pages_group = None

        if base_dict is not None:
            self.update(**base_dict)

        self.set_task_id(task_id)

        # An already loaded exam (e.g. a DetailView's self.object) saves a query
        self.set_exam(exam if exam is not None else exam_pk)

        self.set_user_id(user_id)
        self.set_user_allowed(user_allowed)

        self.set_nav_url(nav_url)

        self.set_tabs(tabs)
        self.set_curr_tab(curr_tab)

        self.set_pages_group(pages_group)

    def as_dict(self) -> dict[str, Any]:
        """Returns the fully built view context as a dictionary, without the values that were never set."""
        return {
            key: value
            for key, value in self.__dict__.items()
            if value is not None
        }

    def update(self, **kwargs: Any) -> None:
        """Adds or updates any kind of attributes, ignoring None values."""
        self.__dict__.update({
            key: value
            for key, value in kwargs.items()
            if value is not None
        })

    def set_exam(self, exam: Exam | int | None) -> None:
        """
        Sets the opened exam (exam_selected) and the common exam of its group (exam): the exam itself when it
        isn't part of a group. Takes the opened exam, or its pk.
        """
        if exam is None:
            return

        if not isinstance(exam, Exam):
            exam = Exam.objects.get(pk=exam)

        self.exam_selected = exam
        self.exam = exam.get_overall_exam_or_default()

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
        """Sets the tabs shown in the view."""
        if tabs is not None:
            self.tabs = tabs

    def set_curr_tab(self, curr_tab: str | None = None) -> None:
        """Sets the current tab."""
        if curr_tab is not None:
            self.curr_tab = curr_tab

    def set_pages_group(self, pages_group: PagesGroup | None = None) -> None:
        """Sets the pages group."""
        if pages_group is not None:
            self.pages_group = pages_group

    def set_task_id(self, task_id: str | None = None) -> None:
        """Sets the task ID."""
        if task_id is not None:
            self.task_id = task_id