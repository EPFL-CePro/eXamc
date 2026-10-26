import json
from typing import Any, ClassVar

from django.views.generic import DetailView

from examc_app.mixins import ExamPermissionAndRedirectMixin
from examc_app.models import Exam, ExamUser, PagesGroup
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.review_functions import get_copies_pages_by_group
from examc_app.utils.view_context_helpers import ViewContext
from examc_app.views.review_views import ReviewUnrecognizedScansBlockMixin


class ReviewView(ExamPermissionAndRedirectMixin, ReviewUnrecognizedScansBlockMixin, DetailView):
    model = Exam
    template_name = 'review/review.html'
    pk_url_kwarg = 'exam_pk'
    perm_codenames: ClassVar = ['manage', 'review']

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        exam = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(exam, self.request.user.id):
            pages_groups = None
            if self.request.user.is_superuser:
                pages_groups = exam.pagesGroup.all()
            else:
                user_exam = ExamUser.objects.filter(exam=exam, user=self.request.user)
                if user_exam:
                    pages_groups = user_exam.first().pages_groups.all()

            context['user_allowed'] = True
            context['nav_url'] = "review_view"
            context['exam_pages_group_list'] = pages_groups
            context['exam_selected'] = exam
            exam = exam.get_overall_exam_or_default()

            context['exam'] = exam
            return context
        else:
            context['user_allowed'] = False
            context['nav_url'] = "review_view"
            context['exam'] = exam
            return context


class ReviewGroupView(ExamPermissionAndRedirectMixin, ReviewUnrecognizedScansBlockMixin, DetailView):
    """
    View for managing review groups for a specific exam.

    This class-based view handles the display and management of review group settings for a particular exam. It allows
    administrators to configure page groups for the exam.

    :param model (Exam): The model class associated with the view.
    :param template_name : The name of the template used for rendering the view.

    Methods:
        get_context_data: Overrides the base class method to provide additional context data for rendering the view.
        post: Handles POST requests for updating review settings.
    """
    model = Exam
    template_name = 'review/review_group.html'
    pk_url_kwarg = 'exam_pk'
    perm_codenames: ClassVar = ['manage', 'review']

    def get_context_data(self, **kwargs) -> dict[str, Any]:
        pages_group = PagesGroup.objects.get(pk=self.kwargs.get("group_pk"))
        current_page = self.kwargs["currpage"]

        # exam_selected is the reviewed exam, exam its group's overall exam (set by ViewContext)
        view_context = ViewContext(
            base_dict=super().get_context_data(),
            nav_url="review_group",
            exam_pk=pages_group.exam.pk,
            pages_group=pages_group,
        )

        # user is not allowed
        if not user_allowed(pages_group.exam, self.request.user.id):
            return view_context.as_dict()

        view_context.set_user_allowed(True)

        # Get scans file path dict by pages groups
        copies_pages_list = get_copies_pages_by_group(pages_group)
        view_context.update(
            copies_pages_list=copies_pages_list,
            json_copies_pages_list=json.dumps(copies_pages_list),
            currpage=current_page,
        )

        # grading scheme
        grading_schemes = None
        if pages_group.use_grading_scheme:
            grading_schemes = pages_group.gradingSchemes.all()

        current_grading_scheme = self.kwargs['current_grading_scheme']
        if grading_schemes and not current_grading_scheme:
            current_grading_scheme = grading_schemes.first()

        view_context.update(
            grading_schemes=grading_schemes,
            current_grading_scheme=current_grading_scheme
        )

        return view_context.as_dict()