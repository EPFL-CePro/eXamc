import json
from typing import Any, ClassVar

from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views.generic import DetailView

from examc_app.mixins import ExamPermissionAndRedirectMixin
from examc_app.models import Exam, ExamUser, PagesGroup
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.review_functions import (
    find_copy_position_in_group,
    get_accessible_pages_groups,
    get_adjacent_pages_group,
    get_copies_pages_by_group,
    get_grading_scheme_invalid_reason,
)
from examc_app.utils.view_context_helpers import ViewContext
from examc_app.views.review_views import ReviewUnrecognizedScansBlockMixin


class ReviewView(ExamPermissionAndRedirectMixin, ReviewUnrecognizedScansBlockMixin, DetailView):
    model = Exam
    template_name = "review/review_summary.html"
    pk_url_kwarg = "exam_pk"
    perm_codenames: ClassVar = ["manage", "review"]

    def get_context_data(self, **kwargs):
        base_context = super().get_context_data(**kwargs)

        view_context = ViewContext(
            base_dict=base_context, exam=self.object, nav_url="review_view"
        )

        if not user_allowed(self.object, self.request.user.id):
            return view_context.as_dict()

        view_context.set_user_allowed(True)

        if self.request.user.is_superuser:
            pages_groups = self.object.pagesGroup.all()
        else:
            exam_user = ExamUser.objects.filter(exam=self.object, user=self.request.user).first()
            pages_groups = exam_user.pages_groups.all() if exam_user else PagesGroup.objects.none()

        view_context.update(exam_pages_group_list=pages_groups)
        return view_context.as_dict()


class ReviewGroupView(
    ExamPermissionAndRedirectMixin, ReviewUnrecognizedScansBlockMixin, DetailView
):
    """
    View for reviewing a pages group of a specific exam.

    Displays the scans of every copy in the group and, when the group uses grading schemes, one tab per
    scheme. The selected scheme's panel is loaded by htmx for the copy shown (review_grading_scheme_panel).

    :param model (Exam): The model class associated with the view.
    :param template_name : The name of the template used for rendering the view.

    Methods:
        get_context_data: Overrides the base class method to provide additional context data for rendering the view.
    """

    model = Exam
    template_name = "review/review_group.html"
    pk_url_kwarg = "exam_pk"
    perm_codenames: ClassVar = ["manage", "review"]

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        pages_group = get_object_or_404(PagesGroup, pk=self.kwargs.get("group_pk"))
        query_string = self.request.GET

        page_id = query_string.get("page_id", 0)

        # exam_selected is the reviewed exam, exam its group's overall exam (set by ViewContext)
        view_context = ViewContext(
            base_dict=super().get_context_data(**kwargs),
            nav_url="review_group",
            exam_pk=pages_group.exam.pk,
            pages_group=pages_group,
            collapse_sidebar=True
        )

        # user is not allowed
        if not user_allowed(pages_group.exam, self.request.user.id):
            return view_context.as_dict()

        view_context.set_user_allowed(True)

        # Get scans file path dict by pages groups
        copies_pages_list = get_copies_pages_by_group(pages_group)

        # ?copy_no= opens a given copy (used by the previous/next question buttons); it takes precedence over page_id
        copy_no = query_string.get("copy_no")
        if copy_no:
            position = find_copy_position_in_group(copies_pages_list, copy_no)
            if position is None:
                messages.warning(
                    self.request,
                    f"Copy {copy_no} has no page in {pages_group.group_name}: opened at the first copy.",
                )
            else:
                page_id = position

        view_context.update(
            copies_pages_list=copies_pages_list,
            json_copies_pages_list=json.dumps(copies_pages_list),
            currpage=page_id,
        )

        # grading schemes: one tab each; the panel of the selected one is loaded by htmx
        use_grading_scheme = False
        if pages_group.use_grading_scheme:
            grading_schemes = list(pages_group.gradingSchemes.all())

            if grading_schemes:
                use_grading_scheme = True

                # A scheme whose marks can't reach the maximum is shown but not selectable
                scheme_tabs = [
                    {
                        "scheme": gs,
                        "invalid_reason": get_grading_scheme_invalid_reason(gs),
                    }
                    for gs in grading_schemes
                ]

                # Open on the first usable scheme; fall back to the first one if none is usable
                usable = [tab["scheme"] for tab in scheme_tabs if not tab["invalid_reason"]]

                view_context.update(
                    grading_schemes=grading_schemes,
                    scheme_tabs=scheme_tabs,
                    current_grading_scheme=usable[0] if usable else grading_schemes[0],
                )

        view_context.update(
            use_grading_scheme=use_grading_scheme,
            next_pages_group=get_adjacent_pages_group(
                pages_group, 1, self.request.user
            ),
            previous_pages_group=get_adjacent_pages_group(
                pages_group, -1, self.request.user
            ),
            question_pages_groups=get_accessible_pages_groups(
                pages_group.exam, self.request.user
            ),
        )

        return view_context.as_dict()