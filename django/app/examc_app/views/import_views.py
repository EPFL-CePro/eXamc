from typing import Any, ClassVar

from django.http import HttpRequest, HttpResponse
from django.urls import reverse
from django.views.generic import DetailView

from examc_app.mixins import ExamPermissionAndRedirectMixin
from examc_app.models import Exam
from examc_app.services.import_data.upload import get_upload_scan_pending_context
from examc_app.services.review.unrecognized_scans import (
    build_unrecognized_review_scan_context,
)
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.view_context_helpers import ViewContext

# Stands for the task id in upload_status_url_template; the page puts its own in place (TASK_ID_PLACEHOLDER).
TASK_ID_PLACEHOLDER = "00000000-0000-0000-0000-000000000000"


class ExamImportView(ExamPermissionAndRedirectMixin, DetailView):
    model = Exam
    template_name = "import/import.html"
    perm_codenames: ClassVar = ["manage"]
    pk_url_kwarg = "exam_pk"
    redirect_enabled = True

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        exam: Exam = self.object

        return self.render_to_response(self.get_context_data(object=exam))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        exam: Exam = self.object

        view_context = ViewContext(
            base_dict=super().get_context_data(**kwargs),
            nav_url="import"
        )
        view_context.set_exam(exam=exam)

        if not user_allowed(exam, self.request.user.id):
            return view_context.as_dict()

        view_context.set_user_allowed(True)

        # task_id (of a running import), pending_amc_import and upload_task_active,
        # from what set_pending_amc_import stored for this exam.
        pending = get_upload_scan_pending_context(self.request, exam.pk)

        # A running import's status URL: the page then locks the upload form and follows the import,
        # with its progress and a cancel button, as if the upload had just been made.
        upload_status_url = ""
        if pending["task_id"]:
            upload_status_url = reverse(
                "upload_scans_status",
                kwargs={"exam_pk": exam.pk, "task_id": pending["task_id"]},
            )

        # non-standard view context arguments
        view_context.update(
            unrecognized_review_scans=build_unrecognized_review_scan_context(exam),
            # import/_import_types/review.html shows the scans upload form only once a project is imported.
            upload_status_url=upload_status_url,
            # The status URL of the task the page will start: it follows it before the upload request answers.
            upload_status_url_template=reverse(
                "upload_scans_status",
                kwargs={"exam_pk": exam.pk, "task_id": TASK_ID_PLACEHOLDER},
            ),
            pending_amc_import=bool(pending["pending_amc_import"]),
            upload_task_active=bool(pending["upload_task_active"]),
        )

        return view_context.as_dict()
