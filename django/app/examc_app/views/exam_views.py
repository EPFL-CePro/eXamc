import json
import logging
from datetime import date
from decimal import Decimal
from typing import Any, ClassVar

from django.contrib.auth.models import Group, User
from django.core.exceptions import BadRequest
from django.db import transaction
from django.db.models import Sum
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DetailView

from examc_app.decorators import exam_permission_required
from examc_app.forms.scale import ScaleForm
from examc_app.mixins import ExamPermissionAndRedirectMixin
from examc_app.models import (
    REVIEWER_GROUP_ID,
    AcademicYear,
    Exam,
    ExamUser,
    PagesGroup,
    Question,
    QuestionType,
    Scale,
    Semester,
)
from examc_app.services.exam.common import build_overall_exam_code
from examc_app.services.exam.paths import get_exam_subdir, update_exam_folders
from examc_app.tasks import generate_statistics
from examc_app.utils.epflldap import ldap_search
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.results_statistics_functions import (
    update_common_exams_questions,
    update_common_exams_scales,
    update_common_exams_users,
)
from examc_app.utils.view_context_helpers import ViewContext

logger = logging.getLogger(__name__)

class ExamInfoView(ExamPermissionAndRedirectMixin, DetailView):
    model = Exam
    template_name = "exam/exam_info.html"
    perm_codenames: ClassVar = ["manage"]
    pk_url_kwarg = "exam_pk"
    redirect_enabled = True

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        exam: Exam = self.object

        # The user's role in this exam, else in one of its common exams: a reviewer goes to the review instead
        exam_users = list(
            ExamUser.objects.filter(user=request.user, exam__in=[exam, *exam.common_exams.all()])
        )
        exam_user = next((role for role in exam_users if role.exam_id == exam.pk), exam_users[0] if exam_users else None)

        if exam_user and not request.user.is_superuser and exam_user.group_id == REVIEWER_GROUP_ID:
            return redirect("review_view", exam_pk=exam.pk)

        return self.render_to_response(self.get_context_data(object=exam))

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        exam: Exam = self.object
        # What belongs to the whole group (permissions, questions) is read from the overall exam
        overall = exam.get_overall_exam_or_default()

        view_context = ViewContext(base_dict=super().get_context_data(**kwargs), nav_url="exam_info")
        if not user_allowed(overall, self.request.user.id):
            return view_context.as_dict()

        # The opened exam: the sidebar and the page show this one
        view_context.set_exam(exam.pk)
        view_context.set_task_id(self.kwargs.get("task_id"))
        view_context.set_user_allowed(True)

        view_context.update(
            question_types=QuestionType.objects.all(),
            sum_questions_points=overall.questions.filter(removed_from_common=False).aggregate(Sum("max_points")),
            users_groups_add=Group.objects.filter(pk__in=[2, 3, 4]),
            semesters=Semester.objects.all(),
            years=AcademicYear.objects.all(),
        )
        return view_context.as_dict()

@exam_permission_required(['manage'])
@require_POST
def ldap_search_exam_user_by_email(request, exam_pk: int):
    """
    Search in LDAP by email.

    This function is used to search for a new reviewer in the ldap database. The email of the reviewer will
    give the complete name of the user and his email.

    Args:
        request: The HTTP request object containing the email address ('email') and the exam ID ('pk').
        exam_pk: The primary key of the exam.

    Returns:
        HttpResponse: A response string containing user information or an indication of existence.
    """
    email = request.POST['email']
    user = ExamUser.objects.filter(user__email=email, exam__id=exam_pk).all()
    if user:
        return HttpResponse("exist")

    django_user = User.objects.filter(email=email).first()
    if django_user:
        entry_str = f"{django_user.username};{django_user.first_name};{django_user.last_name};{email}"
        return HttpResponse(entry_str)

    user_entry = ldap_search.get_entry(email, 'mail')
    if user_entry:
        entry_str = user_entry['uniqueidentifier'][0] + ";"  + user_entry['givenName'][0] + ";" + user_entry['sn'][
            0] + ";" + email
        return HttpResponse(entry_str)
    else:
        return JsonResponse(
            {"error": "not_found"},
            status=400
        )


@exam_permission_required(['manage'])
@require_POST
def update_exam_users(request: HttpRequest, exam_pk: int):
    """
    Add new users to an exam.

    This function is used to add new users to an exam

    Args:
        request: The HTTP request object.
        exam_pk: The primary key of the exam.
    """
    exam = request.exam
    users_list = request.POST.getlist('users_list[]')

    #reviewer_group, created = Group.objects.get_or_create(name='Reviewer')
    for user_in in users_list:
        user_list = user_in.split(";")

        if user_list[0].startswith('delete_'):
            user_to_delete = User.objects.filter(email=user_list[3]).first()
            exam_user = ExamUser.objects.get(user=user_to_delete,exam=exam)
            exam_user.delete()
        else:
            users = User.objects.filter(email=user_list[3]).all()
            if users:
                user = users.first()
            else:
                user = User()
                user.username = user_list[0]
                user.first_name = user_list[1]
                user.last_name = user_list[2]
                user.email = user_list[3]
                user.save()

            exam_user, _created = ExamUser.objects.get_or_create(user=user, exam=exam)
            exam_user.group = Group.objects.get(pk=user_list[4])
            if exam_user.group.id in [2,3,4] and not exam_user.pages_groups:
                exam_user.pages_groups.set(PagesGroup.objects.filter(exam=exam).all())
            exam_user.save()

    return redirect('exam_info', exam_pk=exam.pk)


@exam_permission_required(['manage'])
@require_POST
def update_exam_info(request, exam_pk: int):
    """
    Update exam info.

    This function is used to update exam info

    Args:
        request: The HTTP request object.
        exam_pk: The primary key of the exam to be updated.
    """

    exam = request.exam

    # This looks if the exam's directory changes after updating its info. If it does, it renames them to the new value.
    # In the past, data from the exam was used for naming the directory (e.g. "CEPRO_001_20241030"). We now use the
    # primary key from the exam DB entry to not have to move the directory after its date changes, for example.
    # This code verifies that the new way is used, and renames the directory to the exam's PK if it's not already.
    current_folder_path = get_exam_subdir(exam)
    logger.info(f"Exam {exam.pk} - current path: {current_folder_path}")

    # Date
    exam_date = request.POST.get("date")
    if not exam_date: raise BadRequest("Exam date is required")
    try:
        exam_date = date.fromisoformat(exam_date)
    except ValueError:
        raise BadRequest("Exam date is not a valid date")
    exam.date = exam_date

    # Code
    exam_code = request.POST.get("code")
    if not exam_code: raise BadRequest("Exam code is required")
    exam.code = exam_code

    # Name
    exam_name = request.POST.get("name")
    if not exam_name: raise BadRequest("Exam name is required")
    exam.name = exam_name

    # Semester's ID
    exam_semester_id = request.POST.get("semester_id")
    if not exam_semester_id: raise BadRequest("Exam semester is required")
    exam.semester_id = exam_semester_id

    # Year's ID
    exam_year_id = request.POST.get("year_id")
    if not exam_year_id: raise BadRequest("Exam year is required")
    exam.year_id = exam_year_id

    # the new type of folder path is created even if it already exists
    new_folder_path = get_exam_subdir(exam, force_by_id_dir=True)

    if current_folder_path != new_folder_path:
        with transaction.atomic():
            logger.info(f"Exam {exam.pk} updated - path: {new_folder_path} (from {current_folder_path})")
            update_exam_folders(current_folder_path, new_folder_path)
    else:
        logger.info(f"Exam {exam.pk} unchanged - path: {new_folder_path}")

    exam.save()

    return redirect('exam_info', exam_pk=exam.pk)


class ScaleCreateView(ExamPermissionAndRedirectMixin, CreateView):
    template_name = 'exam/scale_create.html'
    model = Scale
    #fields = ['name', 'total_points', 'points_to_add', 'min_grade','max_grade', 'rounding']#,'formula']
    form_class = ScaleForm
    perm_codenames: ClassVar = ['manage']
    pk_url_kwarg = 'exam_pk'

    def form_valid(self, form):
        scale = form.save(commit=False)
        scale.save()
        exam = Exam.objects.get(pk=self.kwargs['exam_pk'])
        exam.scales.add(scale)
        exam.save()

        for comex in exam.common_exams.all():
            scale_comex, created = Scale.objects.get_or_create(exam=comex,name = scale.name, total_points=scale.total_points)
            if created:
                scale_comex.total_points = scale.total_points
                scale_comex.points_to_add = scale.points_to_add
                scale_comex.min_grade = scale.min_grade
                scale_comex.max_grade = scale.max_grade
                scale_comex.rounding = scale.rounding
                scale_comex.formula = scale.formula
                scale_comex.save()

        task = generate_statistics.delay(exam.pk)
        task_id = task.task_id

        return HttpResponseRedirect(reverse('exam_info_with_task', kwargs={'exam_pk': exam.pk, 'task_id': task_id}))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['exam_pk'] = self.kwargs['exam_pk']
        return context

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        exam = get_object_or_404(Exam, pk=self.kwargs["exam_pk"])
        total = exam.questions.filter(removed_from_common=False).aggregate(total=Sum("max_points"))["total"]
        if total is not None:
            # The sum has the questions' precision: rounded to the scale's (e.g. 16.00000 -> 16.00)
            places = Scale._meta.get_field("total_points").decimal_places
            initial["total_points"] = total.quantize(Decimal(1).scaleb(-places))
        return initial


@exam_permission_required(['manage'])
@require_POST
def delete_exam_scale(request, scale_pk, exam_pk: int):
    scale_to_delete = Scale.objects.get(pk=scale_pk)
    exam_to_manage = Exam.objects.get(pk=exam_pk)

    exam_to_manage.scales.remove(scale_to_delete)
    exam_to_manage.save()

    scale_to_delete.delete()

    # delete scale in other commons
    for comex in exam_to_manage.common_exams.all():
        scale_to_del_comex = Scale.objects.filter(exam__pk=comex.pk, name=scale_to_delete.name).first()
        if scale_to_del_comex:
            comex.scales.remove(scale_to_del_comex)
            comex.save()
            scale_to_del_comex.delete()

    task = generate_statistics.delay(exam_pk)
    task_id = task.task_id

    return HttpResponseRedirect(reverse('exam_info_with_task', kwargs={'exam_pk': exam_pk, 'task_id': task_id}))



@exam_permission_required(['manage'])
@require_POST
def set_final_scale(request, scale_pk, exam_pk: int, all_common=0):
    final_scale = Scale.objects.get(id=scale_pk)

    for scale in final_scale.exam.scales.all():
        if scale == final_scale:
            scale.final = True
        else:
            scale.final = False
        scale.save()

    if all_common == 1:
        for comex in final_scale.exam.common_exams.all():
            for comex_scale in comex.scales.all():
                if comex_scale.name == final_scale.name:
                    comex_scale.final = True
                else:
                    comex_scale.final = False
                comex_scale.save()

    return redirect(reverse('exam_info', kwargs={'exam_pk': str(final_scale.exam.pk)}))



@exam_permission_required(['manage'])
@require_POST
def update_exam_options(request,exam_pk: int):
    exam = request.exam
    exam.review_option = False
    exam.amc_option = False
    exam.res_and_stats_option = False
    exam.prep_option = False
    if f"review_option_{exam_pk}" in request.POST:
        exam.review_option = True
    if f"amc_option_{exam_pk}" in request.POST:
        exam.amc_option = True
    if f"res_and_stats_option_{exam_pk}" in request.POST:
        exam.res_and_stats_option = True
    if f"prep_option_{exam_pk}" in request.POST:
        exam.prep_option = True

    exam.save()
    return HttpResponse('ok')


# QUESTIONS MANAGEMENT
# ------------------------------------------
# @exam_permission_required(['manage'])
# def update_question(request,exam_pk: int):
#     question = Question.objects.get(pk=request.POST['question_pk'])
#     field_name = request.POST['field']
#     value = request.POST['value']
#     setattr(question, field_name, value)
#     question.save()
#
#     return HttpResponse(1)



@exam_permission_required(['manage'])
@require_POST
def update_questions(request, exam_pk: int):
    data = json.loads(request.POST.get('data'))

    for question in data:
        quest = Question.objects.get(pk=question['QUESTION'])
        if 'ANSWERS' in question:
            quest.nb_answers = question['ANSWERS']
        quest.max_points = question['MAX POINTS']
        if quest.question_type_id != question['TYPE']:
            old_qtype = quest.question_type_id
            quest.question_type_id = question['TYPE']
            if quest.question_type_id in (1,2) and quest.nb_answers == 0 or old_qtype == 3:
                quest.nb_answers = 4
            elif quest.question_type_id == 3:
                quest.nb_answers = 2
            else:
                quest.nb_answers = 0
        if 'COMMON' in question:
            quest.common = bool(question['COMMON'])
            quest.removed_from_common = not question['COMMON']
        quest.save()

    return HttpResponse(1)

@exam_permission_required(['manage'])
@require_POST
def set_common_exam(request: HttpRequest, exam_pk: int):
    exam = get_object_or_404(Exam, pk=exam_pk)

    # get or create overall exam if not from overall exam
    if exam.is_overall():
        return HttpResponseRedirect(reverse('exam_info', kwargs={ 'exam_pk': exam.pk }))

    overall_code = build_overall_exam_code(exam)
    overall_exam, new_exam_was_created = Exam.objects.get_or_create(
        code=overall_code,
        semester=exam.semester,
        year=exam.year
    )

    if new_exam_was_created:
        overall_exam.name = 'COMMON'
        overall_exam.pdf_catalog_name = exam.pdf_catalog_name
        overall_exam.date = exam.date
        overall_exam.overall = True
        overall_exam.res_and_stats_option = True
        overall_exam.save()

    exam.common_exams.add(overall_exam)
    exam.save()

    update_common_exams_questions(overall_exam.pk)
    update_common_exams_scales(overall_exam.pk)
    update_common_exams_users(overall_exam.pk)

    task = generate_statistics.delay(overall_exam.pk)
    task_id = task.task_id

    return HttpResponseRedirect(reverse('exam_info_with_task', kwargs={'exam_pk': overall_exam.pk, 'task_id': task_id}))

@exam_permission_required(['manage'])
@require_POST
def validate_common_exams_settings(request,exam_pk: int):
    overall_exam = request.exam
    common_exams_ids = request.POST.getlist(str(exam_pk) + '_common_to[]')
    if common_exams_ids:
        common_exams = Exam.objects.filter(id__in=common_exams_ids)
        overall_exam.common_exams.set(common_exams)
        overall_exam.save()

        update_common_exams_questions(overall_exam.pk)
        update_common_exams_scales(overall_exam.pk)
        update_common_exams_users(overall_exam.pk)

        task = generate_statistics.delay(overall_exam.pk)
        task_id = task.task_id

        return HttpResponseRedirect(reverse('exam_info_with_task', kwargs={'exam_pk': overall_exam.pk, 'task_id': task_id}))
    else:
        redirect_exam = overall_exam.common_exams.first()
        for exam in overall_exam.common_exams.all():
            exam.common_exams.clear()
        overall_exam.delete()
        return redirect('../exam-info/' + str(redirect_exam.pk))
