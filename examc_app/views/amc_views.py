import sqlite3

from django.contrib import messages
from django.shortcuts import render, redirect
from examc_app.utils.review_functions import *
from examc_app.utils.amc_functions import *
from examc_app.forms import *
from examc_app.models import *

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, FileResponse, HttpRequest, HttpResponseRedirect, HttpResponseForbidden,HttpResponseBadRequest, JsonResponse

import json

@login_required
def upload_amc_project(request, pk):
    exam = Exam.objects.get(pk=pk)

    if request.method == 'POST':
        if 'amc_project_zip_file' not in request.FILES:
            message = "No zip file provided."
            return render(request, 'amc/upload_amc_project.html', {'exam': exam,'message': message})

        zip_file = request.FILES['amc_project_zip_file']
        file_name = f"exam_{exam.pk}_amc_project.zip"
        temp_file_path = os.path.join(settings.AUTOUPLOAD_ROOT, file_name)

        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

        with open(temp_file_path, 'wb') as temp_file:
            for chunk in zip_file.chunks():
                temp_file.write(chunk)

        zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year) + "_" + str(exam.semester) + "_" + exam.code
        tmp_extract_path = zip_path + "/tmp_extract"

        # extract zip file in tmp dir
        with zipfile.ZipFile(temp_file_path, 'r') as zip_ref:
            print("start extraction")
            zip_ref.extractall(tmp_extract_path)

        if not os.path.isfile(tmp_extract_path+"/options.xml"):
            dirs = [entry for entry in os.listdir(tmp_extract_path) if os.path.isdir(os.path.join(tmp_extract_path, entry))]
            tmp_extract_path += "/"+dirs[0]
            if not os.path.isfile(tmp_extract_path+"/options.xml"):
                return render(request, 'amc/upload_amc_project.html', {
                    'exam': exam,
                    'message': 'The zip file does not contains options.xml file in the two first level of folders !'
                })

        # move to destination amc_projects
        amc_project_path = get_amc_project_path(exam,True)
        shutil.move(tmp_extract_path, amc_project_path)

        return render(request, 'amc/upload_amc_project.html', {
            'exam': exam,
            'message': 'AMC project folder uploaded !'
        })

    return render(request, 'amc/upload_amc_project.html', {'exam': exam})

@login_required
def amc_view(request, pk):
    exam = Exam.objects.get(pk=pk)

    amc_data_path = get_amc_project_path(exam,False)

    if amc_data_path:
        amc_data_path += "/data/"
        amc_data_url = get_amc_project_url(exam)
        con = sqlite3.connect(amc_data_path+"capture.sqlite")
        cur = con.cursor()


        # Attach scoring db
        cur.execute("ATTACH DATABASE '"+amc_data_path+"scoring.sqlite' as scoring")

        select_amc_pages_str = ("SELECT "
                                "   student as copy,"
                                "   page as page, "
                                "   mse as mse, "
                                "   REPLACE(src,'%PROJET','"+amc_data_url+"') as source, "
                                "   (SELECT 10*(0.007 - MIN(ABS(1.0 * cz.black / cz.total - 0.007))) / 0.007 FROM capture_zone cz WHERE cz.student = cp.student AND cz.page = cp.page) as sensitivity " 
                                "FROM capture_page cp "
                                "ORDER BY copy, page")

        query = cur.execute(select_amc_pages_str)

        colname_pages = [d[0] for d in query.description]
        data_pages = [dict(zip(colname_pages, r)) for r in query.fetchall()]

        for data in data_pages:
            query = cur.execute("SELECT DISTINCT(id_a), "
                                "sc.why as why "
                                "FROM capture_zone cz "
                                "INNER JOIN scoring.scoring_score sc ON sc.student = "+str(data['copy'])+" AND sc.question = cz.id_a "
                                "WHERE type = 4 "
                                "AND cz.student = "+ str(data['copy']) +
                                " AND cz.page = " + str(data['page']))
            colname_questions_id = [d[0] for d in query.description]
            data_questions_id = [dict(zip(colname_questions_id, r)) for r in query.fetchall()]
            questions_ids=''
            for qid in data_questions_id:
                questions_ids+='%'+str(qid['id_a'])
                if qid['why'] == 'E':
                    questions_ids+='|INV|'
                elif qid['why'] == 'V':
                    questions_ids+='|EMP|'

            data['questions_ids'] = questions_ids+'%'

        cur.close()
        cur.connection.close()

        con = sqlite3.connect(amc_data_path+"layout.sqlite")
        cur = con.cursor()
        select_amc_questions_str = ("SELECT * FROM layout_question")

        query = cur.execute(select_amc_questions_str)

        colname_questions = [d[0] for d in query.description]
        data_questions = [dict(zip(colname_questions, r)) for r in query.fetchall()]

        cur.close()
        cur.connection.close()

        # get project dir list
        project_dir_info = get_project_dir_info(exam)
        project_dir_dict = project_dir_info[0]
        project_dir_files_list = project_dir_info[1]

        # get amc options and infos
        amc_option_nb_copies = get_amc_option_by_key(exam,'nombre_copies')
        amc_update_documents_msg = get_amc_update_document_info(exam)
        amc_layout_detection_msg = get_amc_layout_detection_info(exam)
        amc_exam_pdf_path = get_amc_exam_pdf_path(exam)
        amc_catalog_pdf_path = get_amc_catalog_pdf_path(exam)

    context = {}
    if user_allowed(exam, request.user.id):
        context['exam'] = exam
        context['user_allowed'] = True
        if amc_data_path:
            context['number_of_copies'] = amc_option_nb_copies
            context['exam_pdf_path'] = amc_exam_pdf_path
            context['catalog_pdf_path'] = amc_catalog_pdf_path
            context['update_documents_msg'] = amc_update_documents_msg
            context['layout_detection_msg'] = amc_layout_detection_msg
            context['data_pages'] = data_pages
            context['data_questions'] = data_questions
            context['project_dir_dict'] = project_dir_dict
            context['project_dir_files_list'] = project_dir_files_list
    else:
        context['user_allowed'] = False


    return render(request, 'amc/amc.html',  context)

@login_required
def get_amc_marks_positions(request):

    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    copy = request.POST['copy']
    page = request.POST['page']

    amc_data_path = get_amc_project_path(exam,False)

    if amc_data_path:
        amc_data_path += "/data/"
        con = sqlite3.connect(amc_data_path+"capture.sqlite")
        cur = con.cursor()

        # Attach scoring db
        cur.execute("ATTACH DATABASE '"+amc_data_path+"scoring.sqlite' as scoring")

        select_mark_position_str = ("SELECT cp.zoneid, "
                                    "cp.corner, "
                                    "cp.x, "
                                    "cp.y, "
                                    "cz.manual,"
                                    "cz.black, "
                                    "sc.why "
                                    "FROM capture_position cp "
                                    "INNER JOIN capture_zone cz ON cz.zoneid = cp.zoneid "
                                    "INNER JOIN scoring.scoring_score sc ON sc.student = "+str(copy)+" AND sc.question = cz.id_a "
                                    "WHERE cp.zoneid in "
                                    "   (SELECT cz2.zoneid from capture_zone cz2 WHERE cz2.student = "+str(copy)+" AND cz2.page = "+str(page)+") "
                                    "AND cp.type = 1 "
                                    "AND cz.type = 4 "
                                    "ORDER BY cp.zoneid, cp.corner ")

        query = cur.execute(select_mark_position_str)

        colname_positions = [d[0] for d in query.description]
        data_positions = [dict(zip(colname_positions, r)) for r in query.fetchall()]

        cur.close()
        cur.connection.close()
        return HttpResponse(json.dumps(data_positions))

    return HttpResponse('')

@login_required
def update_amc_mark_zone(request):
    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    zoneid = request.POST['zoneid']

    amc_data_path = get_amc_project_path(exam,False)

    if amc_data_path:
        amc_data_path += "/data/"
        con = sqlite3.connect(amc_data_path+"capture.sqlite")
        cur = con.cursor()

        select_mark_zone_str = ("SELECT manual FROM capture_zone WHERE zoneid = " + str(zoneid))

        query = cur.execute(select_mark_zone_str)

        colname_zones = [d[0] for d in query.description]
        data_zones = [dict(zip(colname_zones, r)) for r in query.fetchall()]

        print(data_zones)

        manual = data_zones[0]['manual']
        if manual == -1.0 or manual == 1.0:
            manual = "0.0"
        else:
            manual = "1.0"

        update_mark_zone_str = ("UPDATE capture_zone SET manual = " + manual + " WHERE zoneid = " + str(zoneid))

        cur.execute(update_mark_zone_str)
        con.commit()

        cur.close()
        con.close()

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