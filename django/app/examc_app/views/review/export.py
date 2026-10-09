import logging
import os

from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from examc_app.decorators import exam_permission_required
from examc_app.forms.results_statistics import ExportMarkedFilesForm
from examc_app.models import Exam
from examc_app.tasks import generate_marked_files_zip
from examc_app.utils.global_functions import user_allowed
from examc_app.views.review_views import block_review_until_unrecognized_scans_assigned

logger = logging.getLogger(__name__)

@exam_permission_required(['manage'])
@block_review_until_unrecognized_scans_assigned
def generate_marked_files(request: HttpRequest, exam_pk: int, task_id: str | None = None):
    """
    Export all the marked files.

    :arg request: TThe HTTP request object.
    :arg exam_pk: The primary key of the exam.
    :arg task_id: The task id of the export marked files task.

    :return: A rendered HTML page and the zipped folder if the user is allowed to export the file.
    """
    exam = Exam.objects.get(pk=exam_pk)

    if user_allowed(exam, request.user.id):

        if request.method == 'POST':
            form = ExportMarkedFilesForm(request.POST, exam=exam)

            if form.is_valid():
                task = generate_marked_files_zip.delay(exam.pk, request.POST['export_type'],
                                                       request.POST['with_comments'])
                task_id = task.task_id

                form = ExportMarkedFilesForm()

                exam_selected = exam
                exam = exam.get_overall_exam_or_default()
                return render(request, 'review/export/export_marked_files.html', {"user_allowed": True,
                                                                                  "form": form,
                                                                                  "exam_selected": exam_selected,
                                                                                  "exam": exam,
                                                                                  "nav_url": "generate_marked_files",
                                                                                  "task_id": task_id})

                # zip_file = open(generated_marked_files_zip_path, 'rb')
                # return FileResponse(zip_file)

            else:
                logger.info("INVALID")
                logger.info(form.errors)
                return HttpResponseRedirect(request.path_info)

        # if a GET (or any other method) we'll create a blank form
        else:
            form = ExportMarkedFilesForm()
            exam_selected = exam
            exam = exam.get_overall_exam_or_default()
            return render(request, 'review/export/export_marked_files.html', {"user_allowed": True,
                                                                              "form": form,
                                                                              "exam": exam,
                                                                              "exam_selected": exam_selected,
                                                                              "nav_url": "generate_marked_files"})
    else:
        exam_selected = exam
        exam = exam.get_overall_exam_or_default()
        return render(request, 'review/export/export_marked_files.html', {"user_allowed": False,
                                                                          "form": None,
                                                                          "exam": exam,
                                                                          "exam_selected": exam_selected,
                                                                          "nav_url": "generate_marked_files"})


@exam_permission_required(['manage'])
def download_marked_files(request: HttpRequest, filename, exam_pk: int):
    exam = get_object_or_404(Exam, pk=exam_pk)
    if os.path.basename(filename) != filename or not filename.endswith(".zip"):
        raise Http404("Invalid filename")

    expected_prefix = f"marked_{exam.year.code}_{exam.semester.code}_{exam.code}_"
    if not filename.startswith(expected_prefix):
        raise Http404("Invalid export file")

    export_root = os.path.realpath(str(settings.EXPORT_TMP_ROOT))
    file_path = os.path.realpath(os.path.join(export_root, filename))
    if not file_path.startswith(export_root + os.sep) or not os.path.isfile(file_path):
        raise Http404("Export file not found")

    return FileResponse(open(file_path, 'rb'))
