import shutil
from decimal import Decimal

from MySQLdb.constants.ER import NONEXISTING_TABLE_GRANT
from django.contrib.auth.decorators import login_required
from django.db.models import Max
#
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from django.conf import settings

from examc_app.decorators import exam_permission_required
from examc_app.forms import CreateExamProjectForm, SummernoteForm, PrepSectionForm, \
    PrepQuestionForm, PrepQuestionAnswerForm, ExamFirstPageForm, CreatePrepQuestionForm, PrepScoringFormulaFormSet
from examc_app.models import *
from examc_app.utils.amc_functions import get_amc_project_path
from examc_app.utils.global_functions import get_course_teachers_string, add_course_teachers_ldap, user_allowed, \
    convert_html_to_latex, exam_generate_preview
from examc_app.utils.preparation_html_to_latex_functions import render_first_page_tex_from_html
from examc_app.views import logger


@login_required
def create_exam_project(request):
    if request.method == 'POST':
        form = CreateExamProjectForm(request.POST)
        if form.is_valid():
            course_id = form.cleaned_data['course']
            date = form.cleaned_data['date']
            year_id = form.cleaned_data['year']
            semester_id = form.cleaned_data['semester']
            # date_text = date.strftime('%d.%m.%Y')
            # duration_text = form.cleaned_data['durationText']
            # language = form.cleaned_data['language']

            semester = Semester.objects.get(pk=semester_id)
            year = AcademicYear.objects.get(pk=year_id)
            course = Course.objects.get(pk=course_id)
            # exam_text = course.code+" - "+course.name
            # teachers_text = get_course_teachers_string(course.teachers)
            teachers = add_course_teachers_ldap(course.teachers)

            # user = request.user
            # if not user in teachers:
            #     teachers.append(user)

            exam = Exam()
            exam.code = course.code
            exam.name = course.name
            exam.semester = semester
            exam.year = year
            exam.date = date
            # exam.amc_option = True
            exam.save()
            for teacher in teachers:
                exam_user = ExamUser()
                exam_user.user = teacher
                exam_user.exam = exam
                exam_user.group_id = 2
                exam_user.save()

            # copy template to new amc_project directory
            # amc_project_template_path = str(settings.AMC_PROJECTS_ROOT)+"/templates/"+language+"/base"
            # new_project_path = str(settings.AMC_PROJECTS_ROOT)+"/"+year.code+"/"+str(semester.code)+"/"+exam.code+"_"+date.strftime("%Y%m%d")
            # shutil.copytree(amc_project_template_path,new_project_path)

            # update exam-info.tex
            # exam_info_path = new_project_path+"/exam-info.tex"
            # with open(exam_info_path, 'r') as file:
            #     file_contents = file.read()
            #     updated_contents = file_contents.replace("<TEACHER>", teachers_text).replace("<PAGES>", "8").replace("<DURATION>", duration_text).replace("<DATE>", date_text).replace("<EXAM>", exam_text)
            #
            #
            # with open(exam_info_path, 'w') as file:
            #     file.write(updated_contents)

            return redirect('examInfo', exam_pk=exam.pk)
        else:
            logger.info("INVALID")
            logger.info(form.errors)
            return render(request, 'exam/create_exam_project.html', {"user_allowed": True,
                                                                     "form": form,
                                                                     "nav_url": "create_exam_project"})

    # if a GET (or any other method) we'll create a blank form
    else:
        form = CreateExamProjectForm(request.POST)

        return render(request, 'exam/create_exam_project.html', {"user_allowed": True,
                                                                 "form": form,
                                                                 "nav_url": "create_exam_project"})


# -------------------------
# Helpers
# -------------------------

def _build_question_forms(section):
    return {
        question.id: PrepQuestionForm(
            instance=question
        )
        for question in section.prepQuestions.all().order_by("position", "pk")
    }


def _build_answer_forms(question):
    return {
        answer.id: PrepQuestionAnswerForm(
            instance=answer
        )
        for answer in question.prepAnswers.all().order_by("position", "pk")
    }


# -------------------------
# Main page
# -------------------------

@exam_permission_required(["manage"])
def exam_preparation_view(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    first_page_form = ExamFirstPageForm(instance=exam)
    sections = exam.prepSections.all().order_by("position", "pk")

    for section in sections:
        section.form = PrepSectionForm(instance=section, prefix=f"section-{section.pk}")

        section.questions = list(section.prepQuestions.all().order_by("position", "pk"))

        for question in section.questions:
            question.form = PrepQuestionForm(
                instance=question,
                prefix=f"question-{question.pk}",
            )


            question.answers = list(question.prepAnswers.all().order_by("position", "pk"))

            for answer in question.answers:
                answer.form = PrepQuestionAnswerForm(
                    instance=answer,
                    prefix=f"answer-{answer.pk}",
                )

    return render(request, "exam/preparation/exam_preparation.html", {
        "exam_selected": exam,
        "fp_txt_form": first_page_form,
        "sections": sections,
        "nav_url": "exam_preparation",
    })


# -------------------------
# First page
# -------------------------

@exam_permission_required(["manage"])
def prep_first_page_panel(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    if request.method == "POST":
        form = ExamFirstPageForm(request.POST, instance=exam)
        saved = form.is_valid()
        if saved:
            form.save()
            exam.refresh_from_db()

            amc_project_path = get_amc_project_path(exam,False)
            html = exam.first_page_text
            first_page_latex_path = amc_project_path+"/first_page.tex"
            first_page_latex_path_output = amc_project_path+"/first_page_generated.tex"
            render_first_page_tex_from_html(html,first_page_latex_path,first_page_latex_path_output)


    else:
        form = ExamFirstPageForm(instance=exam)
        saved = False

    return render(
        request,
        "exam/preparation/_prep_first_page_panel.html",
        {
            "exam_selected": exam,
            "fp_txt_form": form,
            "saved": saved,
        },
    )


# -------------------------
# Sections
# -------------------------

@exam_permission_required(["manage"])
def prep_sections_list(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)
    sections = exam.prepSections.all().order_by("position", "pk")

    section_items = [
        {
            "section": section,
            "section_form": PrepSectionForm(instance=section, prefix=f"section-{section.pk}"),
        }
        for section in sections
    ]

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            "section_items": section_items,
        },
    )


@exam_permission_required(["manage"])
def prep_section_panel(request, exam_pk, section_id):
    section = get_object_or_404(PrepSection, pk=section_id, exam_id=exam_pk)
    prefix = f"section-{section.pk}"

    if request.method == "POST":
        form = PrepSectionForm(request.POST, instance=section, prefix=prefix)
        if form.is_valid():
            form.save()
            section.refresh_from_db()
    else:
        form = PrepSectionForm(instance=section, prefix=prefix)

    questions = section.prepQuestions.all().order_by("position", "pk")

    return render(request, "exam/preparation/_prep_section_card.html", {
        "exam_selected": section.exam,
        "section": section,
        "section_form": form,
        "questions": questions,
        "expanded": True,
    })


@exam_permission_required(["manage"])
def reorder_prep_sections(request, exam_pk):
    if request.method != "POST":
        return HttpResponseBadRequest("Invalid method")

    exam = get_object_or_404(Exam, pk=exam_pk)

    try:
        payload = json.loads(request.body)
        sections_data = payload.get("sections", [])
    except (json.JSONDecodeError, TypeError):
        return HttpResponseBadRequest("Invalid JSON")

    section_map = {
        section.id: section
        for section in exam.prepSections.all()
    }

    for item in sections_data:
        try:
            section_id = int(item["id"])
            position = int(item["position"])
        except (KeyError, TypeError, ValueError):
            continue

        section = section_map.get(section_id)
        if section:
            section.position = position
            section.save(update_fields=["position"])

    sections = exam.prepSections.all().order_by("position", "pk")
    for section in sections:
        section.form = PrepSectionForm(instance=section)

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            "sections": sections,
        },
    )


@exam_permission_required(["manage"])
def add_prep_section(request, exam_pk):
    exam = get_object_or_404(Exam, pk=exam_pk)

    next_position = (exam.prepSections.count() or 0) + 1

    section = PrepSection.objects.create(
        exam=exam,
        title="New section",
        section_text="",
        position=next_position,
    )

    section_form = PrepSectionForm(instance=section, prefix=f"section-{section.pk}")
    questions = section.prepQuestions.all().order_by("position", "pk")

    return render(
        request,
        "exam/preparation/_prep_section_card.html",
        {
            "exam_selected": exam,
            "section": section,
            "section_form": section_form,
            "questions": questions,
            "expanded": True,
        },
    )


@exam_permission_required(["manage"])
def delete_prep_section(request, exam_pk, section_id):
    exam = get_object_or_404(Exam, pk=exam_pk)
    section = get_object_or_404(PrepSection, pk=section_id, exam=exam)

    section.delete()

    sections = list(exam.prepSections.all().order_by("position", "pk"))

    for index, section in enumerate(sections, start=1):
        if section.position != index:
            section.position = index
            section.save(update_fields=["position"])
        section.form = PrepSectionForm(instance=section, prefix=f"section-{section.pk}")

    return render(
        request,
        "exam/preparation/_prep_sections_list.html",
        {
            "exam_selected": exam,
            "sections": sections,
        },
    )


# -------------------------
# Questions
# -------------------------

@exam_permission_required(["manage"])
def prep_question_panel(request, exam_pk, question_id):
    question = get_object_or_404(PrepQuestion, pk=question_id, prep_section__exam_id=exam_pk)
    prefix = f"question-{question.pk}"

    if request.method == "POST":
        form = PrepQuestionForm(request.POST, instance=question, prefix=prefix)
        saved = form.is_valid()
        if saved:
            form.save()
            question.refresh_from_db()
    else:
        form = PrepQuestionForm(instance=question, prefix=prefix)
        saved = False

    answers = list(question.prepAnswers.all().order_by("position", "pk"))
    for answer in answers:
        answer.form = PrepQuestionAnswerForm(
            instance=answer,
            prefix=f"answer-{answer.pk}",
        )

    return render(
        request,
        "exam/preparation/_prep_question_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "section": question.prep_section,
            "question": question,
            "question_form": form,
            "answers": answers,
            "saved": saved,
        },
    )


@exam_permission_required(["manage"])
def add_prep_question(request, exam_pk, section_id):
    exam = get_object_or_404(Exam, pk=exam_pk)
    section = get_object_or_404(PrepSection, pk=section_id, exam=exam)

    if request.method == "POST":
        form = CreatePrepQuestionForm(request.POST)

        if form.is_valid():
            question_type = form.cleaned_data["question_type"]
            nb_answers = form.cleaned_data.get("nb_answers") or 0
            title = form.cleaned_data.get("title") or "New question"

            next_position = (section.prepQuestions.aggregate(max_pos=Max("position"))["max_pos"] or 0) + 1

            question = PrepQuestion.objects.create(
                prep_section=section,
                question_type=question_type,
                title=title,
                question_text="",
                position=next_position,
            )

            if question_type.code in ["SCQ", "MCQ"]:
                for i in range(nb_answers):
                    PrepQuestionAnswer.objects.create(
                        prep_question=question,
                        title=f"Answer {i + 1}",
                        answer_text="",
                        is_correct=False,
                        position=i + 1,
                    )

            elif question_type.code == "TF":
                PrepQuestionAnswer.objects.create(
                    prep_question=question,
                    title="TRUE",
                    answer_text="TRUE",
                    is_correct=False,
                    position=1,
                )
                PrepQuestionAnswer.objects.create(
                    prep_question=question,
                    title="FALSE",
                    answer_text="FALSE",
                    is_correct=False,
                    position=2,
                )

            questions = list(section.prepQuestions.all().order_by("position", "pk"))

            for q in questions:
                q.form = PrepQuestionForm(
                    instance=q,
                    prefix=f"question-{q.pk}",
                )
                q.answers = list(q.prepAnswers.all().order_by("position", "pk"))
                for answer in q.answers:
                    answer.form = PrepQuestionAnswerForm(
                        instance=answer,
                        prefix=f"answer-{answer.pk}",
                    )

            return render(
                request,
                "exam/preparation/_prep_questions_list.html",
                {
                    "exam_selected": exam,
                    "section": section,
                    "questions": questions,
                },
            )

        return render(
            request,
            "exam/preparation/_prep_add_question_form.html",
            {
                "exam_selected": exam,
                "form": form,
                "section": section,
            },
        )

    elif request.method == "GET":
        form = CreatePrepQuestionForm(initial={"section_pk": section_id})

        return render(
            request,
            "exam/preparation/_prep_add_question_form.html",
            {
                "exam_selected": exam,
                "form": form,
                "section": section,
            },
        )

    return HttpResponse("")


@exam_permission_required(["manage"])
def delete_prep_question(request, exam_pk, question_id):
    question = get_object_or_404(PrepQuestion, pk=question_id, prep_section__exam_id=exam_pk)
    section = question.prep_section
    question.delete()

    questions = list(section.prepQuestions.all().order_by("position", "pk"))

    for index, q in enumerate(questions, start=1):
        if q.position != index:
            q.position = index
            q.save(update_fields=["position"])

        q.form = PrepQuestionForm(
            instance=q,
            prefix=f"question-{q.pk}",
        )
        q.answers = list(q.prepAnswers.all().order_by("position", "pk"))
        for answer in q.answers:
            answer.form = PrepQuestionAnswerForm(
                instance=answer,
                prefix=f"answer-{answer.pk}",
            )

    return render(
        request,
        "exam/preparation/_prep_questions_list.html",
        {
            "exam_selected": section.exam,
            "section": section,
            "questions": questions,
        },
    )


# -------------------------
# Answers
# -------------------------

@exam_permission_required(["manage"])
def prep_answers_block(request, exam_pk, question_id):
    question = get_object_or_404(PrepQuestion, pk=question_id, prep_section__exam_id=exam_pk)
    answers = list(question.prepAnswers.all().order_by("position", "pk"))

    for answer in answers:
        answer.form = PrepQuestionAnswerForm(
            instance=answer,
            prefix=f"answer-{answer.pk}",
        )

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": answers,
        },
    )


@exam_permission_required(["manage"])
def prep_answer_panel(request, exam_pk, answer_id):
    answer = get_object_or_404(PrepQuestionAnswer, pk=answer_id, prep_question__prep_section__exam_id=exam_pk)
    prefix = f"answer-{answer.pk}"

    if request.method == "POST":
        form = PrepQuestionAnswerForm(request.POST, instance=answer, prefix=prefix)
        saved = form.is_valid()
        if saved:
            form.save()
            answer.refresh_from_db()
    else:
        form = PrepQuestionAnswerForm(instance=answer, prefix=prefix)
        saved = False

    return render(
        request,
        "exam/preparation/_prep_answer_row.html",
        {
            "exam_selected": answer.prep_question.prep_section.exam,
            "question": answer.prep_question,
            "answer": answer,
            "answer_form": form,
            "saved": saved,
        },
    )


@exam_permission_required(["manage"])
def add_prep_answer(request, exam_pk, question_id):
    question = get_object_or_404(PrepQuestion, pk=question_id, prep_section__exam_id=exam_pk)

    next_position = (question.prepAnswers.aggregate(max_pos=Max("position"))["max_pos"] or 0) + 1

    PrepQuestionAnswer.objects.create(
        prep_question=question,
        title="New answer",
        answer_text="",
        is_correct=False,
        position=next_position,
    )

    answers = list(question.prepAnswers.all().order_by("position", "pk"))
    for answer in answers:
        answer.form = PrepQuestionAnswerForm(
            instance=answer,
            prefix=f"answer-{answer.pk}",
        )

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": answers,
        },
    )


@exam_permission_required(["manage"])
def delete_prep_answer(request, exam_pk, answer_id):
    answer = get_object_or_404(PrepQuestionAnswer, pk=answer_id, prep_question__prep_section__exam_id=exam_pk)
    question = answer.prep_question
    answer.delete()

    answers = list(question.prepAnswers.all().order_by("position", "pk"))

    for index, ans in enumerate(answers, start=1):
        if ans.position != index:
            ans.position = index
            ans.save(update_fields=["position"])

        ans.form = PrepQuestionAnswerForm(
            instance=ans,
            prefix=f"answer-{ans.pk}",
        )

    return render(
        request,
        "exam/preparation/_prep_answers_block.html",
        {
            "exam_selected": question.prep_section.exam,
            "question": question,
            "answers": answers,
        },
    )


@exam_permission_required(["manage"])
def exam_preview_pdf(request, exam_pk):
    # exam = Exam.objects.get(pk=exam_pk)
    # result = exam_generate_preview(exam)
    # return HttpResponse(result)
    return HttpResponse("")


def _get_scoring_formula_scope(prep_section=None, prep_question=None, prep_answer=None):
    if prep_answer:
        return "answer"
    if prep_question:
        return "question"
    if prep_section:
        return "section"
    return "exam"


def _get_scoring_formula_queryset(exam_pk, prep_section=None, prep_question=None, prep_answer=None):
    queryset = PrepScoringFormula.objects.filter(exam_id=exam_pk)

    if prep_answer:
        queryset = queryset.filter(prep_answer_id=prep_answer)

    elif prep_question:
        queryset = queryset.filter(
            prep_question_id=prep_question,
            prep_answer__isnull=True,
        )

    elif prep_section:
        queryset = queryset.filter(
            prep_section_id=prep_section,
            prep_question__isnull=True,
            prep_answer__isnull=True,
        )

    else:
        queryset = queryset.filter(
            prep_section__isnull=True,
            prep_question__isnull=True,
            prep_answer__isnull=True,
        )

    return queryset.order_by("pk")


@exam_permission_required(["manage"])
def scoring_formulas_modal(request, exam_pk):
    if request.method == "GET":
        prep_section = request.GET.get("prep_section") or None
        prep_question = request.GET.get("prep_question") or None
        prep_answer = request.GET.get("prep_answer") or None

        scope = _get_scoring_formula_scope(
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        queryset = _get_scoring_formula_queryset(
            exam_pk=exam_pk,
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        formset = PrepScoringFormulaFormSet(
            queryset=queryset,
            form_kwargs={"scope": scope},
        )

        return render(request, "exam/preparation/_prep_scoring_formulas_modal_body.html", {
            "formset": formset,
            "exam_pk": exam_pk,
            "prep_section": prep_section,
            "prep_question": prep_question,
            "prep_answer": prep_answer,
            "scope": scope,
        })

    elif request.method == "POST":
        prep_section = request.POST.get("prep_section") or None
        prep_question = request.POST.get("prep_question") or None
        prep_answer = request.POST.get("prep_answer") or None

        scope = _get_scoring_formula_scope(
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        queryset = _get_scoring_formula_queryset(
            exam_pk=exam_pk,
            prep_section=prep_section,
            prep_question=prep_question,
            prep_answer=prep_answer,
        )

        formset = PrepScoringFormulaFormSet(
            request.POST,
            queryset=queryset,
            form_kwargs={"scope": scope},
        )

        if formset.is_valid():
            instances = formset.save(commit=False)

            # Delete rows marked for deletion
            for obj in formset.deleted_objects:
                obj.delete()

            # Save or update current rows
            for instance in instances:
                if not instance.formula:
                    continue

                instance.exam_id = exam_pk

                if scope == "exam":
                    instance.prep_section = None
                    instance.prep_question = None
                    instance.prep_answer = None

                elif scope == "section":
                    instance.prep_section_id = prep_section
                    instance.prep_question = None
                    instance.prep_answer = None

                elif scope == "question":
                    instance.prep_section = None
                    instance.prep_question_id = prep_question
                    instance.prep_answer = None

                elif scope == "answer":
                    instance.prep_section = None
                    instance.prep_question = None
                    instance.prep_answer_id = prep_answer

                instance.save()

            return JsonResponse({
                "success": True,
                "message": "Formulas saved successfully."
            })

        html = render(
            request,
            "exam/preparation/_prep_scoring_formulas_modal_body.html",
            {
                "formset": formset,
                "exam_pk": exam_pk,
                "prep_section": prep_section,
                "prep_question": prep_question,
                "prep_answer": prep_answer,
                "scope": scope,
            }
        ).content.decode("utf-8")

        return JsonResponse({
            "success": False,
            "html": html
        })

    return JsonResponse({
        "success": False,
        "message": "Invalid request method."
    }, status=400)

@exam_permission_required(["manage"])
def delete_scoring_formula(request, exam_pk, pk):
    if request.method != "POST":
        return JsonResponse({
            "success": False,
            "message": "Invalid request method."
        }, status=405)

    obj = get_object_or_404(PrepScoringFormula, pk=pk, exam_id=exam_pk)
    obj.delete()

    return JsonResponse({
        "success": True,
        "message": "Scoring formula deleted successfully."
    })

# #######################################################################################
# @exam_permission_required(['manage'])
# def exam_preparation_view(request, exam_pk):
#     def exam_preparation_view(request, exam_pk):
#         exam = Exam.objects.get(pk=exam_pk)
#         first_page_form = ExamFirstPageForm(
#             instance=exam,
#             field_id="id_summernote_exam_first_page"
#         )
#         return render(
#             request,
#             "exam/preparation/exam_preparation.html",
#             {
#                 "exam": exam,
#                 "fp_txt_form": first_page_form,
#                 "user_allowed": True,
#                 "nav_url": "exam_preparation",
#             },
#         )
#
# def exam_preparation_view(request, exam_pk):
#     exam = Exam.objects.get(pk=exam_pk)
#     first_page_form = ExamFirstPageForm(
#         instance=exam,
#         field_id="id_summernote_exam_first_page"
#     )
#     return render(
#         request,
#         "exam/preparation/exam_preparation.html",
#         {
#             "exam": exam,
#             "fp_txt_form": first_page_form,
#             "user_allowed": True,
#             "nav_url": "exam_preparation",
#         },
#     )
#
# @exam_permission_required(['manage'])
# def prep_section_panel(request, exam_pk, section_id):
#     section = PrepSection.objects.get(pk=section_id)
#
#     if request.method == "POST":
#         form = PrepSectionForm(
#             request.POST,
#             instance=section,
#             field_id=f"id_summernote_section_{section.id}"
#         )
#         saved = form.is_valid()
#         if saved:
#             form.save()
#     else:
#         form = PrepSectionForm(
#             instance=section,
#             field_id=f"id_summernote_section_{section.id}"
#         )
#         saved = False
#
#     return render(
#         request,
#         "exam/preparation/_prep_section_card.html",
#         {
#             "exam": section.exam,
#             "section": section,
#             "section_form": form,
#             "saved": saved,
#         },
#     )
#
# @exam_permission_required(['manage'])
# def prep_question_panel(request, exam_pk, question_id):
#     question = PrepQuestion.objects.get(pk=question_id)
#
#     if request.method == "POST":
#         form = PrepQuestionForm(
#             request.POST,
#             instance=question,
#             field_id=f"id_summernote_question_{question.id}"
#         )
#         saved = form.is_valid()
#         if saved:
#             form.save()
#     else:
#         form = PrepQuestionForm(
#             instance=question,
#             field_id=f"id_summernote_question_{question.id}"
#         )
#         saved = False
#
#     return render(
#         request,
#         "exam/preparation/_prep_question_block.html",
#         {
#             "exam": question.prep_section.exam,
#             "section": question.prep_section,
#             "question": question,
#             "question_form": form,
#             "saved": saved,
#         },
#     )
#
# @exam_permission_required(['manage'])
# def prep_question_answers(request, exam_pk, question_id):
#     question = PrepQuestion.objects.get(pk=question_id)
#     answers = question.prepAnswers.all().order_by("position", "pk")
#
#     answer_forms = {
#         answer.id: PrepQuestionAnswerForm(
#             instance=answer,
#             field_id=f"id_summernote_answer_{answer.id}"
#         )
#         for answer in answers
#     }
#
#     return render(
#         request,
#         "exam/preparation/_prep_answers_block.html",
#         {
#             "exam": question.prep_section.exam,
#             "question": question,
#             "answers": answers,
#             "answer_forms": answer_forms,
#             "saved": False,
#         },
#     )
#
# @exam_permission_required(['manage'])
# def add_prep_section(request, exam_pk):
#     exam = Exam.objects.get(pk=exam_pk)
#
#     next_pos = (exam.prepSections.aggregate(Max("position"))["position__max"] or 0) + 1
#     PrepSection.objects.create(
#         exam=exam,
#         title="New section",
#         description="",
#         position=next_pos,
#     )
#
#     sections = exam.prepSections.all().order_by("position", "pk")
#     return render(
#         request,
#         "exam/preparation/_prep_sections_list.html",
#         {
#             "exam": exam,
#             "sections": sections,
#         },
#     )
#
# @exam_permission_required(['manage'])
# def delete_prep_question(request, exam_pk, question_id):
#     question = PrepQuestion.objects.get(pk=question_id)
#     section = question.prep_section
#     question.delete()
#
#     section.refresh_from_db()
#
#     return render(
#         request,
#         "exam/preparation/_prep_section_questions.html",
#         {
#             "exam": section.exam,
#             "section": section,
#             "questions": section.prepQuestions.all().order_by("position", "pk"),
#         },
#     )
#
# @login_required
# def exam_add_section_question(request,exam_pk):
#     if request.method == 'POST':
#         form = CreateQuestionForm(request.POST)
#         if form.is_valid():
#             section_pk = form.cleaned_data['section_pk']
#             question_type_pk = form.cleaned_data['question_type']
#             nb_answers = form.cleaned_data['nb_answers']
#
#             section = PrepSection.objects.get(pk=section_pk)
#             exam = Exam.objects.get(pk=exam_pk)
#             question_type = QuestionType.objects.get(pk=question_type_pk)
#
#             # get new question code
#             last_question = Question.objects.filter(section=section, question_type=question_type).order_by(
#                 'code').all().last()
#             if last_question:
#                 last_number = int(last_question.code.split('-')[1]) + 1
#             else:
#                 last_number = 1
#             last_number = str(last_number).zfill(2)
#
#             # create question
#             question = Question()
#             question.exam = exam
#             question.section = section
#             question.code = question_type.code+"-"+last_number
#             question.question_type = question_type
#             question.save()
#
#             # create answers
#             if question_type.code in ['SCQ','MCQ']:
#                 for i in range(nb_answers):
#                     answer = QuestionAnswer()
#                     answer.code = chr(ord('@')+(i+1))
#                     answer.question = question
#                     answer.save()
#             elif question_type.code == 'TF':
#                 answer = QuestionAnswer()
#                 answer.code = 'TRUE'
#                 answer.question = question
#                 answer.answer_text = 'TRUE'
#                 answer.save()
#                 answer = QuestionAnswer()
#                 answer.code = 'FALSE'
#                 answer.question = question
#                 answer.answer_text = 'FALSE'
#                 answer.save()
#             else:
#                 open_max_points = form.cleaned_data['open_max_points']
#                 open_points_increment = Decimal(form.cleaned_data['open_points_increment'])
#                 answers_range = int(open_max_points / open_points_increment) + 1
#                 for i in range(answers_range):
#                     answer = QuestionAnswer()
#                     answer.code = i
#                     answer.question = question
#                     answer.answer_text = str(i)
#                     answer.save()
#
#             return redirect('exam_preparation', pk=exam.pk)
#
#         else:
#             logger.info("INVALID")
#             logger.info(form.errors)
#             return render(request, 'exam/create_exam_project.html', {"user_allowed": True,
#                                                                      "form": form,
#                                                                      "nav_url": "create_exam_project"})
#
#     # if a GET (or any other method) we'll create a blank form
#     elif request.method == 'GET':
#         form = CreateQuestionForm(section_pk=request.GET.get('section_pk'))
#
#         return HttpResponse(form.as_p())
#
#     return HttpResponse(None)
#
# @login_required
# def exam_update_section(request):
#     section = PrepSection.objects.get(pk=request.POST.get('section_pk'))
#
#     section.header_text = request.POST.get('header_text')
#     section.title = request.POST.get('section_title')
#     section.save()
#
#     return HttpResponse('ok')
#
# @login_required
# def get_header_section_txt(request):
#     """
#       Get the section header text.
#
#       This view function retrieves the header section text identified by its primary key. It returns
#       the text as an HTTP response.
#
#       Args:
#           request: The HTTP request object containing the primary key 'section_pk' of the section.
#
#       Returns:
#           HttpResponse: An HTTP response containing the text for the section.
#       """
#
#     section = PrepSection.objects.get(pk=request.POST['section_pk'])
#     section_txt_frm = SummernoteForm()
#     section_txt_frm.initial['ckeditor_txt'] = section.header_text
#     return HttpResponse(section.header_text)
#
# @login_required
# def exam_update_question(request):
#     question = Question.objects.get(pk=request.POST.get('question_pk'))
#
#     question.question_text = request.POST.get('question_text')
#     if question.question_type.code == 'OPEN':
#         answer, created = QuestionAnswer.objects.get_or_create(question=question, code='BOX')
#         answer_box_dict = {"box_type":request.POST.get('open_question_box_type'),"box_size":request.POST.get('open_question_box_size')}
#         answer.answer_text = json.dumps(answer_box_dict)
#         answer.question = question
#         answer.save()
#     else:
#         question.formula = request.POST.get('question_formula')
#     question.save()
#
#     return HttpResponse('ok')
#
# @login_required
# def exam_update_answers(request):
#
#     answers = json.loads(request.POST.get('answers'))
#     for a in answers:
#         answer = QuestionAnswer.objects.get(pk=a['answer_pk'])
#         answer.answer_text = a['answer_text']
#         answer.is_correct = a['is_correct']
#         answer.formula = a['answer_formula']
#         answer.save()
#
#     return HttpResponse('ok')
#
# @login_required
# def exam_add_answer(request):
#     if request.method == 'POST':
#         question = Question.objects.get(pk=request.POST.get('question_pk'))
#         nb_answers = question.answers.all().count()
#
#         answer = QuestionAnswer()
#         answer.code = chr(ord('@') + (nb_answers + 1))
#         answer.question = question
#         answer.save()
#
#         exam = question.exam
#
#     return HttpResponse('ok')
#
# @login_required
# def exam_remove_answer(request):
#     answer = QuestionAnswer.objects.get(pk=request.POST.get('answer_pk'))
#     exam = answer.question.exam
#     answer.delete()
#     # redo codes
#     answers = QuestionAnswer.objects.filter(question__pk=answer.question.pk).order_by('code')
#     i = 1
#     for a in answers.all():
#         a.code = chr(ord('@') + (i))
#         a.save()
#         i+=1
#     return HttpResponse('ok')
#
# @login_required
# def exam_remove_question(request, exam_pk):
#     question = Question.objects.get(pk=request.POST.get('question_pk'))
#     question.delete()
#     return HttpResponse('ok')
#
# @login_required
# def exam_remove_section(request, exam_pk):
#     section = ExamSection.objects.get(pk=request.POST.get('section_pk'))
#     section.delete()
#     # redo numbering
#     sections = ExamSection.objects.filter(exam__pk=section.exam.id).order_by('section_number')
#     i = 1
#     for s in sections.all():
#         if s.title == 'Section '+str(s.section_number):
#             s.title = 'Section '+str(i)
#         s.section_number = i
#         s.save()
#         i += 1
#     return HttpResponse('ok')
#
# @login_required
# def exam_update_first_page(request, exam_pk):
#     exam = Exam.objects.get(pk=exam_pk)
#     exam.first_page_text = request.POST.get('first_page_text')
#
#     output = convert_html_to_latex(exam.first_page_text)
#     print(output)
#
#     exam.save()
#     return HttpResponse('ok')
#
# @login_required
