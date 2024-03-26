
from django.shortcuts import render
from examc_app.utils.review_functions import *
from examc_app.utils.amc_functions import *
from examc_app.forms import *
from examc_app.models import *

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, FileResponse

import json

@login_required
def upload_amc_project(request, pk):
    exam = Exam.objects.get(pk=pk)

    if request.method == 'POST':
        if 'amc_project_zip_file' not in request.FILES:
            message = "No zip file provided."
            return render(request, 'amc/upload_amc_project.html', {'exam': exam,'message': message})

        zip_file = request.FILES['amc_project_zip_file']

        message = create_amc_project_dir_from_zip(exam,zip_file)

        return render(request, 'amc/upload_amc_project.html', {
            'exam': exam,
            'message': message
        })

    return render(request, 'amc/upload_amc_project.html', {'exam': exam})

@login_required
def amc_view(request, pk, active_tab=0):
    exam = Exam.objects.get(pk=pk)

    amc_data_path = get_amc_project_path(exam, False)

    context = {}
    if user_allowed(exam, request.user.id):
        context['exam'] = exam
        context['user_allowed'] = True
        if amc_data_path:
            # get amc options and infos
            amc_option_nb_copies = get_amc_option_by_key(exam,'nombre_copies')
            amc_update_documents_msg = get_amc_update_document_info(exam)
            amc_layout_detection_msg = get_amc_layout_detection_info(exam)
            amc_exam_pdf_path = get_amc_exam_pdf_path(exam)
            amc_catalog_pdf_path = get_amc_catalog_pdf_path(exam)

            # get project dir list
            project_dir_info = get_project_dir_info(exam)
            project_dir_dict = project_dir_info[0]
            project_dir_files_list = project_dir_info[1]

            # get data
            data = get_amc_data_capture_manual_data(exam)
            amc_data_capture_summary = get_automatic_data_capture_summary(exam)
            number_of_copies = amc_data_capture_summary[0]
            number_of_incomplete_copies = len(amc_data_capture_summary[1])
            missing_pages = amc_data_capture_summary[1]
            if number_of_incomplete_copies > 0:
                data_capture_message = "Data capture from "+str(number_of_copies-number_of_incomplete_copies)+" complete and "+str(number_of_incomplete_copies)+" incomplete papers"
            else:
                data_capture_message = "Data capture from "+str(number_of_copies)

            context['number_of_copies'] = amc_option_nb_copies
            context['exam_pdf_path'] = amc_exam_pdf_path
            context['catalog_pdf_path'] = amc_catalog_pdf_path
            context['update_documents_msg'] = amc_update_documents_msg
            context['layout_detection_msg'] = amc_layout_detection_msg
            context['project_dir_dict'] = project_dir_dict
            context['project_dir_files_list'] = project_dir_files_list
            context['data_pages'] = data[0]
            context['data_questions'] = data[1]
            context['active_tab'] = active_tab
            context['data_capture_message'] = data_capture_message
            context['missing_pages'] = missing_pages

    else:
        context['user_allowed'] = False


    return render(request, 'amc/amc.html',  context)

@login_required
def amc_data_capture_manual(request,pk):
    exam = Exam.objects.get(pk=pk)

    amc_data_path = get_amc_project_path(exam, False)

    context = {}
    if user_allowed(exam, request.user.id):
        context['exam'] = exam
        context['user_allowed'] = True
        if amc_data_path:

            data = get_amc_data_capture_manual_data(exam)

            context['data_pages'] = data[0]
            context['data_questions'] = data[1]
    else:
        context['user_allowed'] = False

    return render(request, 'amc/amc_data_capture_manual.html', context)

@login_required
def get_amc_marks_positions(request):

    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    copy = request.POST['copy']
    page = request.POST['page']

    data_positions = get_amc_marks_positions_data(exam, copy, page)

    return HttpResponse(json.dumps(data_positions))


@login_required
def update_amc_mark_zone(request):
    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    zoneid = request.POST['zoneid']

    update_amc_mark_zone_data(exam, zoneid)

    return HttpResponse('')

@login_required
def edit_amc_file(request):
    f = open(request.POST['filepath'], 'r')
    file_contents = f.read()
    f.close()
    return HttpResponse(file_contents)

@login_required
def save_amc_edited_file(request):
    data = request.POST['data']
    filepath = request.POST['filepath']
    f = open(filepath, 'r+')
    f.truncate(0)
    f.write(data)
    f.close()
    return HttpResponse(True)

@login_required
def call_amc_update_documents(request):
    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    nb_copies = request.POST['nb_copies']
    result = amc_update_documents(exam,nb_copies)
    if not 'ERR:' in result:
        result = get_amc_update_document_info(exam)
    return HttpResponse(result)

@login_required
def call_amc_layout_detection(request):
    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    result = amc_layout_detection(exam)
    if not 'ERR:' in result:
        result = get_amc_layout_detection_info(exam)
    return HttpResponse(result)

def call_amc_automatic_data_capture(request):
    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    zip_file = request.FILES['amc_scans_zip_file']

    result = amc_automatic_data_capture(exam,zip_file)
    if not 'ERR:' in result:
        return HttpResponse('yes')
    else:
        return HttpResponse(result)

def open_amc_exam_pdf(request,pk):
    exam = Exam.objects.get(pk=pk)
    file_path = get_amc_exam_pdf_path(exam)
    try:
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('not found')

def open_amc_catalog_pdf(request,pk):
    exam = Exam.objects.get(pk=pk)
    file_path = get_amc_catalog_pdf_path(exam)
    try:
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('not found')

@login_required
def view_amc_log_file(request,pk):
    exam = Exam.objects.get(pk=pk)
    amc_log_file_path = get_amc_project_path(exam,False)+"/amc-compiled.log"
    f = open(amc_log_file_path, 'r', encoding='latin-1')
    file_contents = f.read()
    f.close()
    return HttpResponse(file_contents)