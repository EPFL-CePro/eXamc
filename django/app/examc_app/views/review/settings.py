import logging

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import DetailView

from examc_app.decorators import exam_permission_required
from examc_app.forms import (
    GradingSchemeCheckBoxForm,
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
    pages_group_settings_changed,
)
from examc_app.views.review_views import (
    ReviewUnrecognizedScansBlockMixin,
    block_review_until_unrecognized_scans_assigned,
    get_locked_pages_group_ids_for_exam,
)

logger = logging.getLogger(__name__)

class ReviewSettingsView(ExamPermissionAndRedirectMixin, ReviewUnrecognizedScansBlockMixin, DetailView):
    """
    View for managing review settings for a specific exam.

    This class-based view handles the display and management of review settings for a particular exam. It allows
    administrators to configure reviewers and page groups for the exam.

    Methods:
        get_context_data: Overrides the base class method to provide additional context data for rendering the view.
    """
    model = Exam
    template_name = 'review/settings/reviewSettings.html'
    error_msg = None
    pk_url_kwarg = 'exam_pk'
    perm_codenames = ['manage']

    def get_context_data(self, **kwargs):
        """
        Retrieves additional context data for rendering the view.

        This method overrides the base class method to include context data such as formsets and current tab.

        :return: dict: A dictionary containing context data for rendering the view.
        """
        context = super(ReviewSettingsView, self).get_context_data(**kwargs)

        exam = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(exam, self.request.user.id):
            curr_tab = "groups"
            if self.kwargs.get("curr_tab") != '':
                curr_tab = self.kwargs.get("curr_tab")
            formsetReviewers = ReviewersFormSet(queryset=ExamUser.objects.filter(exam=exam, group__pk__in=[2, 3, 4]))

            amc_project_path = get_amc_project_path(exam, False)
            if amc_project_path:
                pages_groups = PagesGroup.objects.filter(exam=exam)
                grading_schemes_pages_groups = PagesGroup.objects.filter(exam=exam, use_grading_scheme=True)
                locked_pages_group_ids = get_locked_pages_group_ids_for_exam(exam)
                amc_data_path = get_amc_project_path(exam, True) + "/data/"
                with AmcLayoutDbManager(
                    amc_data_path=amc_data_path
                ) as amc_layout_db_manager:
                    questions = amc_layout_db_manager.select_questions()
                questions_choices = [(q['name'], q['name']) for q in questions]
                formset_pages_groups = PagesGroupsFormSet(queryset=pages_groups, initial=[
                    {'id': None, 'group_name': 'Select', 'nb_pages': -1}],
                                                          form_kwargs={"questions_choices": questions_choices})

                summernote_media_form = GradingSchemeCheckBoxForm()  # empty instance, just for .media

                context['user_allowed'] = True
                context['nav_url'] = "reviewSettingsView"
                context['exam_reviewers_formset'] = formsetReviewers
                context['exam_pages_groups_formset'] = formset_pages_groups
                context['curr_tab'] = curr_tab
                context['summernote_media_form'] = summernote_media_form
                context['grading_schemes_pages_groups'] = grading_schemes_pages_groups
                context['locked_pages_group_ids'] = locked_pages_group_ids
            else:

                context['user_allowed'] = True
                context['nav_url'] = "reviewSettingsView"
                context['curr_tab'] = curr_tab
                context['locked_pages_group_ids'] = []

            context['exam_selected'] = exam
            exam = exam.get_overall_exam_or_default()
            context['exam'] = exam
            return context
        else:
            context['user_allowed'] = False
            context['nav_url'] = "reviewSettingsView"
            context['exam'] = exam
            return context

    # Define method to handle POST request
    def post(self, *args, **kwargs):
        """
        Handles POST requests for updating review settings.

        This method processes the form submissions for updating reviewers and page groups for the exam.

        :return: HttpResponse: A response containing the updated view or an error message.
        """
        self.object = self.get_object()
        exam = Exam.objects.get(pk=self.kwargs['exam_pk'])
        error_messages = []

        if "submit-reviewers" in self.request.POST:
            curr_tab = "reviewers"
            formset = ReviewersFormSet(self.request.POST)
            if formset.is_valid():
                for form in formset:
                    if form.is_valid() and form.cleaned_data and form.cleaned_data["user"]:
                        examReviewer = form.save(commit=False)
                        examReviewer.exam = exam
                        if "pages_groups" in form.cleaned_data:
                            examReviewer.pages_groups.set(form.cleaned_data["pages_groups"])
                            examReviewer.save()
                            form.save_m2m()
        else:
            curr_tab = "groups"
            amc_data_path = get_amc_project_path(exam, True) + "/data/"
            with AmcLayoutDbManager(
                amc_data_path=amc_data_path
            ) as amc_layout_db_manager:
                questions = amc_layout_db_manager.select_questions()
            questions_choices = [(q['name'], q['name']) for q in questions]
            formset = PagesGroupsFormSet(self.request.POST, form_kwargs={"questions_choices": questions_choices})
            if formset.is_valid():
                for form in formset:
                    if form.is_valid() and form.cleaned_data:
                        pages_group = form.save(commit=False)
                        if form.cleaned_data["nb_pages"] > -1:
                            existing_group = None
                            if pages_group.pk:
                                existing_group = PagesGroup.objects.filter(pk=pages_group.pk, exam=exam).first()
                                if not existing_group or not pages_group_has_review_activity(existing_group):
                                    continue
                                if not pages_group_settings_changed(existing_group, pages_group):
                                    pass
                                else:
                                    error_messages.append(
                                        f"Pages group '{existing_group.group_name}' is locked because review data already exists. "
                                        f"Only grading help can still be edited."
                                    )
                                    continue

                            if not pages_group_name_available(
                                    exam,
                                    pages_group.group_name,
                                    exclude_pages_group_id=pages_group.pk,
                            ):
                                error_messages.append(
                                    f"Question '{pages_group.group_name}' is already used by another pages group."
                                )
                                continue

                            pages_group.exam = exam
                            pages_group.save()
            else:
                logger.warning(formset.errors)
                error_messages.append("Some pages groups are invalid. Please correct the form and retry.")

        error_msg = " ".join(dict.fromkeys(error_messages)) if error_messages else None

        formsetReviewers = ReviewersFormSet(queryset=ExamUser.objects.filter(exam=exam))

        amc_data_path = get_amc_project_path(exam, True) + "/data/"
        with AmcLayoutDbManager(amc_data_path=amc_data_path) as amc_layout_db_manager:
            questions = amc_layout_db_manager.select_questions()
        questions_choices = [(q['name'], q['name']) for q in questions]
        formsetPagesGroups = PagesGroupsFormSet(queryset=PagesGroup.objects.filter(exam=exam), initial=[
            {'id': None, 'group_name': 'Select', 'nb_pages': -1}], form_kwargs={"questions_choices": questions_choices})

        grading_schemes_pages_groups = PagesGroup.objects.filter(exam=exam, use_grading_scheme=True)
        locked_pages_group_ids = get_locked_pages_group_ids_for_exam(exam)

        context = super(ReviewSettingsView, self).get_context_data(**kwargs)
        if user_allowed(exam, self.request.user.id):
            context['user_allowed'] = True
            context['nav_url'] = "reviewSettingsView"
            context['exam_selected'] = exam
            exam = exam.get_overall_exam_or_default()
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formsetPagesGroups
            context['exam_reviewers_formset'] = formsetReviewers
            context['curr_tab'] = curr_tab
            context['grading_schemes_pages_groups'] = grading_schemes_pages_groups
            context['error_msg'] = error_msg
            context['locked_pages_group_ids'] = locked_pages_group_ids
        else:
            context['user_allowed'] = False
            context['nav_url'] = "reviewSettingsView"
            context['exam_selected'] = exam
            exam = exam.get_overall_exam_or_default()
            context['exam'] = exam
            return context

        return self.render_to_response(context=context)


@exam_permission_required(['manage'])
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
    new_group.group_name = 'Select...'
    new_group.nb_pages = -1
    new_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'exam_pk': exam_pk, 'curr_tab': "groups"}))


@exam_permission_required(['manage'])
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
        return redirect(reverse('reviewSettingsView', kwargs={'exam_pk': exam_pk, 'curr_tab': "groups"}))

    pages_group.delete()

    return redirect(reverse('reviewSettingsView', kwargs={'exam_pk': exam_pk, 'curr_tab': "groups"}))


@exam_permission_required(['manage'])
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
    pages_group = get_object_or_404(PagesGroup, pk=request.POST.get('group_pk'), exam_id=exam_pk)
    pages_group.grading_help = request.POST['grading_help']
    pages_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'exam_pk': exam_pk, 'curr_tab': "groups"}))


@exam_permission_required(['manage', 'review'])
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

    pages_group = get_object_or_404(PagesGroup, pk=request.POST.get('group_pk'), exam_id=exam_pk)
    # grading_help_group_form = ckeditorForm()
    # grading_help_group_form.initial['ckeditor_txt'] = pages_group.grading_help

    return HttpResponse(pages_group.grading_help)