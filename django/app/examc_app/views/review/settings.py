import logging
from typing import Any, ClassVar

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import DetailView

from examc_app.decorators import exam_permission_required
from examc_app.forms.review import (
    PagesGroupsFormSet,
    ReviewersFormSet,
)
from examc_app.mixins import ExamPermissionAndRedirectMixin
from examc_app.models import Exam, ExamUser, PagesGroup
from examc_app.utils.amc_db_queries.layout import AmcLayoutDbManager
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.review_settings_guards import (
    pages_group_has_review_activity,
    pages_group_name_available,
)
from examc_app.utils.view_context_helpers import (
    ViewContext,
)
from examc_app.views.review_views import (
    block_review_until_unrecognized_scans_assigned,
    get_locked_pages_group_ids_for_exam,
)

logger = logging.getLogger(__name__)

# Groups whose exam users are listed as reviewers: teachers, reviewers, assistants
REVIEWERS_GROUP_IDS = (2, 3, 4)

# Keys of the {% pill_tab %}s of review_settings.html
QUESTIONS_TAB = "questions"
REVIEWERS_TAB = "exam-reviewers"


def _questions_choices(exam: Exam) -> list[tuple[str, str]]:
    """The questions of the exam's AMC project, as choices of a pages group; none without a project."""
    project_path = get_amc_project_path(exam)
    if not project_path:
        return []
    with AmcLayoutDbManager(amc_data_path=f"{project_path}/data/") as amc_layout_db_manager:
        questions = amc_layout_db_manager.select_questions()
    return [(question["name"], question["name"]) for question in questions]


class ReviewSettingsView(ExamPermissionAndRedirectMixin, DetailView):  # keep the current base classes
    """The review settings of an exam: its pages groups (questions), its reviewers and its grading schemes."""

    model = Exam
    template_name = "review/settings/review_settings.html"
    pk_url_kwarg = "exam_pk"
    perm_codenames: ClassVar = ["manage"]

    # -----------------------------------------------------------------------
    # Page
    # -----------------------------------------------------------------------

    def get_context_data(
        self,
        *,
        curr_tab: str | None = None,
        reviewers_formset: ReviewersFormSet | None = None,
        pages_groups_formset: PagesGroupsFormSet | None = None,
        error_msg: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        The page's context. After a failed save, `post` passes the submitted formset (shown with its errors),
        the tab it was submitted from and the error message; the other formset is a fresh one.
        """
        exam = self._get_exam()

        view_context = ViewContext(
            base_dict=super().get_context_data(**kwargs),
            exam_pk=exam.pk,
            nav_url="review_settings_view",
        )
        # Also used by the sidebar's common exams select, to open the same tab of another exam
        view_context.set_curr_tab(curr_tab or self.request.GET.get("tab") or QUESTIONS_TAB)

        if not user_allowed(exam, self.request.user.id):
            return view_context.as_dict()
        view_context.set_user_allowed(True)

        # Without an AMC project, there are no questions to make pages groups of: the page shows a warning
        if not get_amc_project_path(exam):
            view_context.update(locked_pages_group_ids=[])
            return view_context.as_dict()

        if reviewers_formset is None:
            reviewers_formset = ReviewersFormSet(queryset=self._reviewers_queryset(exam))
        if pages_groups_formset is None:
            pages_groups_formset = PagesGroupsFormSet(
                queryset=PagesGroup.objects.filter(exam=exam),
                initial=[{"id": None, "group_name": "Select", "nb_pages": None}],
                form_kwargs=self._pages_groups_form_kwargs(exam),
            )

        view_context.update(
            exam_reviewers_formset=reviewers_formset,
            exam_pages_groups_formset=pages_groups_formset,
            grading_schemes_pages_groups=PagesGroup.objects.filter(exam=exam, use_grading_scheme=True),
            locked_pages_group_ids=get_locked_pages_group_ids_for_exam(exam),
            error_msg=error_msg,
        )
        return view_context.as_dict()

    # -----------------------------------------------------------------------
    # Saving
    # -----------------------------------------------------------------------

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """
        Saves the reviewers or the pages groups, depending on which form was submitted.
        On success, redirects back to the form's tab, so a page refresh doesn't submit again.
        On errors, renders the page with the submitted formset, so each error is shown next to its field.
        """
        self.object = self.get_object()
        exam = self._get_exam()
        if not user_allowed(exam, request.user.id):
            raise PermissionDenied

        if "submit-reviewers" in request.POST:
            return self._save_reviewers(exam)
        return self._save_pages_groups(exam)

    def _save_reviewers(self, exam: Exam) -> HttpResponse:
        formset = ReviewersFormSet(self.request.POST, queryset=self._reviewers_queryset(exam))

        if not formset.is_valid():
            return self._render_with_errors(
                curr_tab=REVIEWERS_TAB,
                reviewers_formset=formset,
                error_msg="Some reviewers are invalid. Please correct the highlighted fields and retry.",
            )

        with transaction.atomic():
            for form in formset.forms:
                if not form.has_changed():
                    continue
                exam_reviewer = form.save(commit=False)
                exam_reviewer.exam = exam
                exam_reviewer.save()
                form.save_m2m()

        messages.success(self.request, "Reviewers saved.")
        return redirect(self._settings_url(exam, REVIEWERS_TAB))

    def _save_pages_groups(self, exam: Exam) -> HttpResponse:
        formset = PagesGroupsFormSet(
            self.request.POST,
            queryset=PagesGroup.objects.filter(exam=exam),
            form_kwargs=self._pages_groups_form_kwargs(exam),
        )

        # Checked once the fields are valid, before saving anything; is_valid() then sees the added errors
        if formset.is_valid():
            self._check_questions_used_once(exam, formset)

        if not formset.is_valid():
            return self._render_with_errors(
                curr_tab=QUESTIONS_TAB,
                pages_groups_formset=formset,
                error_msg="Some pages groups are invalid. Please correct the highlighted fields and retry.",
            )

        with transaction.atomic():
            for form in formset.forms:
                # Unchanged forms include the empty extra form; locked groups can't change
                if not form.has_changed() or form.locked:
                    continue
                pages_group = form.save(commit=False)
                pages_group.exam = exam
                pages_group.save()

        messages.success(self.request, "Pages groups saved.")
        return redirect(self._settings_url(exam, QUESTIONS_TAB))

    @staticmethod
    def _check_questions_used_once(exam: Exam, formset: PagesGroupsFormSet) -> None:
        """Adds an error to each changed pages group whose question is used by another pages group."""
        used_names: set[str] = set()
        for form in formset.forms:
            if not form.has_changed() or form.locked:
                continue
            name: str = form.cleaned_data["group_name"]
            if name in used_names or not pages_group_name_available(
                exam, name, exclude_pages_group_id=form.instance.pk
            ):
                form.add_error("group_name", f"Question '{name}' is already used by another pages group.")
            used_names.add(name)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _get_exam(self) -> Exam:
        if not isinstance(self.object, Exam):
            raise Http404("Exam not found.")
        return self.object

    def _render_with_errors(self, **context: Any) -> HttpResponse:
        return self.render_to_response(self.get_context_data(**context))

    @staticmethod
    def _reviewers_queryset(exam: Exam):
        return ExamUser.objects.filter(exam=exam, group__pk__in=REVIEWERS_GROUP_IDS)

    @staticmethod
    def _pages_groups_form_kwargs(exam: Exam) -> dict[str, Any]:
        return {
            "questions_choices": _questions_choices(exam),
            "locked_pages_group_ids": get_locked_pages_group_ids_for_exam(exam),
            # A question used by another pages group is disabled in the select
            "used_question_names": list(
                PagesGroup.objects.filter(exam=exam).values_list("group_name", flat=True)
            ),
        }

    @staticmethod
    def _settings_url(exam: Exam, tab: str) -> str:
        return reverse("review_settings_view", kwargs={"exam_pk": exam.pk}, query={"tab": tab})


@exam_permission_required(["manage"])
@block_review_until_unrecognized_scans_assigned
@require_POST
def add_new_pages_group(request: HttpRequest, exam_pk: int):
    """
    Add a new pages group for an exam.

    This view function creates a new pages group for a specific exam. It saves the new group with default values and
    redirects the user back to the review settings page.

    :param request: The HTTP request object.
    :param exam_pk: The primary key of the exam.

    :return: HttpResponseRedirect: A redirect response to the review settings page for the specified exam.

    """
    exam = Exam.objects.get(pk=exam_pk)
    new_group = PagesGroup()
    new_group.exam = exam
    new_group.group_name = "Select..."
    new_group.nb_pages = -1
    new_group.save()

    return redirect(
        reverse(
            "review_settings_view",
            kwargs={"exam_pk": exam_pk},
        )
    )


@exam_permission_required(["manage"])
@block_review_until_unrecognized_scans_assigned
@require_POST
def delete_pages_group(request: HttpRequest, group_pk: int, exam_pk: int):
    """
    Delete a pages group.

    This view function deletes a pages group identified by its primary key. When finished, it redirects the user
    back to the review settings page.

    :param request: The HTTP request object.
    :param group_pk: The primary key of the pages group to delete.
    :param exam_pk: The primary key of the exam associated with the pages group.

    :return: HttpResponseRedirect: A redirect response to the review settings page for the specified exam.
    """
    pages_group = get_object_or_404(PagesGroup, pk=group_pk, exam_id=exam_pk)
    if pages_group_has_review_activity(pages_group):
        messages.error(
            request,
            f"Pages group '{pages_group.group_name}' is locked and cannot be deleted because review data already exists.",
        )
        return redirect(
            reverse(
                "review_settings_view",
                kwargs={"exam_pk": exam_pk},
            )
        )

    pages_group.delete()

    return redirect(
        reverse(
            "review_settings_view",
            kwargs={"exam_pk": exam_pk},
        )
    )


@exam_permission_required(["manage"])
@block_review_until_unrecognized_scans_assigned
@require_POST
def edit_pages_group_grading_help(request: HttpRequest, exam_pk: int):
    """
    Edit the grading help.

    This view function edits the grading help comment. When finished, it redirects the user back to the review settings page.


    :arg request: The HTTP request object.
    :arg exam_pk: The primary key of the exam associated with the pages group.

    :return: HttpResponseRedirect: A redirect response to the review settings page for the specified exam.
    """
    pages_group = get_object_or_404(
        PagesGroup, pk=request.POST.get("group_pk"), exam_id=exam_pk
    )
    pages_group.grading_help = request.POST["grading_help"]
    pages_group.save()

    return redirect(
        reverse(
            "review_settings_view",
            kwargs={"exam_pk": exam_pk},
        )
    )


@exam_permission_required(["manage", "review"])
@block_review_until_unrecognized_scans_assigned
@require_POST
def get_pages_group_grading_help(request: HttpRequest, exam_pk: int):
    """
    Get the grading help.

    This view function retrieves the grading help for a pages group identified by its primary key. It returns
    the grading help as an HTTP response.


    :arg request: The HTTP request object containing the primary key 'pk' of the pages group.
    :arg exam_pk: The primary key of the exam associated with the pages group.

    :return: HttpResponse: An HTTP response containing the grading help for the pages group.
    """

    pages_group = get_object_or_404(
        PagesGroup, pk=request.POST.get("group_pk"), exam_id=exam_pk
    )
    # grading_help_group_form = ckeditorForm()
    # grading_help_group_form.initial['ckeditor_txt'] = pages_group.grading_help

    return HttpResponse(pages_group.grading_help)
