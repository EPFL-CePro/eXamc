import json
import os
import pathlib
from urllib import request

from asgiref.sync import async_to_sync, sync_to_async
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse, Http404, FileResponse, StreamingHttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from examc_app.decorators import exam_permission_required
from examc_app.models import *
from examc_app.tasks import import_csv_data, generate_marked_files_zip
from examc_app.utils.amc_functions import *
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.review_functions import generate_marked_pdfs, create_students_from_amc, get_scans_list


#@login_required
@exam_permission_required(['manage'])
def upload_amc_project(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)

    exam_selected = exam
    if exam.common_exams:
        for common_exam in exam.common_exams.all():
            if common_exam.is_overall():
                exam = common_exam
                break

    if request.method == 'POST':
        if 'amc_project_zip_file' not in request.FILES:
            message = "No zip file provided."
            return render(request, 'amc/upload_amc_project.html', {'exam': exam,'message': message,"nav_url":"upload_amc_project"})

        zip_file = request.FILES['amc_project_zip_file']

        message = create_amc_project_dir_from_zip(exam,zip_file)

        create_students_from_amc(exam)

        return render(request, 'amc/upload_amc_project.html', {
            'exam': exam,
            'exam_selected': exam_selected,
            'nav_url': "upload_amc_project",
            'message': message
        })

    return render(request, 'amc/upload_amc_project.html', {'exam': exam, 'exam_selected': exam_selected,'nav_url': "upload_amc_project"})

#@login_required
@exam_permission_required(['manage'])
def amc_view(request, exam_pk,curr_tab=None, task_id=None):
    exam = Exam.objects.get(pk=exam_pk)

    amc_data_path = get_amc_project_path(exam, False)

    context = {}
    if user_allowed(exam, request.user.id):
        if amc_data_path:
            # get amc options and infos
            amc_option_nb_copies = get_amc_option_by_key(exam,'nombre_copies')
            amc_update_documents_msg = get_amc_update_document_info(exam)
            amc_layout_detection_msg = get_amc_layout_detection_info(exam)
            #amc_exam_pdf_path = get_amc_exam_pdf_path(exam)
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
                data_capture_message = "Data capture from "+str(number_of_copies)+" complete papers"
            nb_unrecognized_pages = amc_data_capture_summary[2]

            overwritten_pages = amc_data_capture_summary[3]

            students_list = get_amc_option_by_key(exam,"listeetudiants").replace("%PROJET/",'')

            has_results = get_amc_results_file_path(exam)

            scans_list = get_scans_list(exam)
            scans_list_json_string = json.dumps(scans_list)

            exam_nb_pages = 1
            if data[0] and len(data[0])>0:
                exam_nb_pages = max(data[0],key=lambda x: float(x['page']))['page']
            context['number_of_copies_param'] = amc_option_nb_copies
            context['copy_count'] = number_of_copies
            #context['exam_pdf_path'] = amc_exam_pdf_path
            context['catalog_pdf_path'] = amc_catalog_pdf_path
            context['update_documents_msg'] = amc_update_documents_msg
            context['layout_detection_msg'] = amc_layout_detection_msg
            context['project_dir_dict'] = project_dir_dict
            context['project_dir_files_list'] = project_dir_files_list
            context['data_pages'] = data[0]
            context['data_questions'] = data[1]
            context['data_copies'] = data[2]
            context['data_capture_message'] = data_capture_message
            context['missing_pages'] = missing_pages
            context['nb_unrecognized_pages'] = nb_unrecognized_pages
            context['overwritten_pages'] = overwritten_pages
            context['students_list'] = students_list
            context['students_list_headers'] = get_students_csv_headers(exam)
            context['auto_assoc_pk'] = get_amc_option_by_key(exam,'liste_key')
            context['auto_assoc_code'] = get_automatic_association_code(exam)
            context['mean'] = get_amc_mean(exam)
            context['questions_scoring_details'] = get_questions_scoring_details_list(exam)
            context['count_missing_assoc'] = get_count_missing_associations(amc_data_path+'/data/')
            context['annotated_papers_available'] = check_annotated_papers_available(exam)
            context['has_results'] = has_results
            context['task_id'] = task_id
            context['curr_tab'] = curr_tab
            context['scans_list_json'] = json.loads(scans_list_json_string)
            context['exam_nb_pages'] = range(1,int(float(exam_nb_pages))+1,1)

        context['exam_selected'] = exam
        if exam.common_exams:
            for common_exam in exam.common_exams.all():
                if common_exam.is_overall():
                    exam = common_exam
                    break
        context['exam'] = exam
        context['user_allowed'] = True
        context['nav_url'] = 'amc_view'

    else:
        context['user_allowed'] = False

    return render(request, 'amc/amc.html',  context)

#@login_required
@exam_permission_required(['manage'])
def amc_data_capture_manual(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)

    amc_data_path = get_amc_project_path(exam, False)

    context = {}
    context['nav_url'] = 'amc_data_capture_manual'
    if user_allowed(exam, request.user.id):

        if amc_data_path:

            data = get_amc_data_capture_manual_data(exam)

            context['data_pages'] = data[0]
            context['data_questions'] = data[1]

        context['exam_selected'] = exam
        if exam.common_exams:
            for common_exam in exam.common_exams.all():
                if common_exam.is_overall():
                    exam = common_exam
                    break
        context['exam'] = exam
        context['user_allowed'] = True
    else:
        context['user_allowed'] = False

    return render(request, 'amc/amc_data_capture_manual.html', context)

#@login_required
@exam_permission_required(['manage'])
def get_amc_marks_positions(request,exam_pk):

    exam = Exam.objects.get(pk=exam_pk)
    copy = request.POST['copy']
    page = request.POST['page']

    data_positions = get_amc_marks_positions_data(exam, copy, page)

    return HttpResponse(json.dumps(data_positions))

@require_POST
@exam_permission_required(['manage'])
def get_unrecognized_pages(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    amc_project_path = get_amc_project_path(exam, False)
    unrecognized_pages = None
    if amc_project_path:
        amc_data_path = amc_project_path + "/data/"

        unrecognized_pages = select_unrecognized_pages(amc_data_path)

        for unrecognized_page in unrecognized_pages:
            file_path = unrecognized_page['filepath']
            if '%HOME' in file_path:
                print("******************* " + str(Path.home()) + " **************************")

                app_home_path = str(settings.BASE_DIR).replace(str(Path.home()), '%HOME')
                file_path = file_path.replace(app_home_path+'/', '')
                print("******************* " + file_path + " **************************")

                # change old file path (www/html/...) to new (srv/examc/private_media/...) from amc db
                file_path = file_path.replace('%HOME/html/eXamc', str(settings.PRIVATE_MEDIA_ROOT))

            file_root = str(settings.SCANS_ROOT)
            if file_path.startswith(str(settings.MARKED_SCANS_ROOT)):
                file_root = str(settings.MARKED_SCANS_ROOT)
            file_path = make_token_for(os.path.relpath(file_path,file_root), file_root)

            unrecognized_page['filepath'] = file_path


    return HttpResponse(json.dumps(unrecognized_pages))

#@login_required
@exam_permission_required(['manage'])
def update_amc_mark_zone(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    zoneid = request.POST['zoneid']
    copy = request.POST['copy']
    page = request.POST['page']

    update_amc_mark_zone_data(exam, zoneid, copy, page)

    return HttpResponse('')

#@login_required
@exam_permission_required(['manage'])
def edit_amc_file(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    amc_project_path = get_amc_project_path(exam, False)
    if request.POST['filepath'] == 'students_list':
        filepath = get_amc_option_by_key(exam,'listeetudiants').replace("%PROJET",get_amc_project_path(exam,False))
        f = open(filepath, 'r')
        file_contents = f.read()
        f.close()
        return HttpResponse(json.dumps([os.path.relpath(filepath, amc_project_path), file_contents]))
    else:
        filepath = amc_project_path + "/" + request.POST['filepath']
        f = open(filepath, 'r', encoding='utf-8')
        file_contents = f.read()
        f.close()
        return HttpResponse(file_contents)

#@login_required
@exam_permission_required(['manage'])
def save_amc_edited_file(request,exam_pk):
    data = request.POST['data']
    exam = Exam.objects.get(pk=exam_pk)
    amc_project_path = get_amc_project_path(exam, False)
    filepath = amc_project_path + "/" + request.POST['filepath']
    if 'is_students_list' in request.POST:
        tmp_filepath = get_amc_project_path(exam,False)+'/_tmp_students.csv'
        shutil.copyfile(filepath, tmp_filepath)
        f = open(tmp_filepath, 'r+', encoding="utf-8")
        f.truncate(0)
        f.write(data)
        f.close()
        check = check_students_csv_file(tmp_filepath)
        if check == 'ok':
            os.rename(tmp_filepath,filepath)
        else:
            os.remove(tmp_filepath)
            check += " -- file not updated !"
        return HttpResponse(check)
    else:
        filepath = amc_project_path + "/" + request.POST['filepath']
        f = open(filepath, 'r+', encoding="utf-8")
        f.truncate(0)
        f.write(data)
        f.close()
        return HttpResponse('ok')

#@login_required
@exam_permission_required(['manage'])
def call_amc_update_documents(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    nb_copies = request.POST['nb_copies']

    result = amc_update_documents(exam,nb_copies,False)

    return HttpResponse(result)

#@login_required
@exam_permission_required(['manage'])
def call_amc_layout_detection(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    result = amc_layout_detection(exam)
    if not 'ERR:' in result:
        result = get_amc_layout_detection_info(exam)
    return HttpResponse(result)

@exam_permission_required(['manage'])
def call_amc_automatic_data_capture(request,from_review,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    zip_file = request.FILES['amc_scans_zip_file']

    return StreamingHttpResponse(amc_automatic_datacapture_subprocess(request, exam,zip_file,False,file_list_path=None))

@exam_permission_required(['manage'])
def import_scans_from_review_pages(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    scans_list = request.POST.getlist('pages_list[]')
    amc_proj_path = get_amc_project_path(exam, False)
    file_list_path = amc_proj_path + "/list-file"
    if os.path.exists(file_list_path):
        os.remove(file_list_path)

    with open(file_list_path, "w") as f:
        for scan in scans_list:
            f.write(scan + "\n")

    return StreamingHttpResponse(amc_automatic_datacapture_subprocess(request, exam, None, True, file_list_path=file_list_path))

@exam_permission_required(['manage'])
def import_scans_from_review(request, exam_pk):
    print('************** importing scans from review')
    exam = Exam.objects.get(pk=exam_pk)

    amc_proj_path = get_amc_project_path(exam, False)
    file_list_path = amc_proj_path + "/list-file"
    if os.path.exists(file_list_path):
        os.remove(file_list_path)

    scans_dir = str(settings.SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(exam.semester.code) + "/" + exam.code+"_"+exam.date.strftime("%Y%m%d")
    print('*********** scans dir: '+scans_dir)
    marked_dir = str(settings.MARKED_SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(
        exam.semester.code) + "/" + exam.code+"_"+exam.date.strftime("%Y%m%d")
    export_subdir = 'marked_' + str(exam.year.code) + "_" + str(
        exam.semester.code) + "_" + exam.code + "_" + datetime.now().strftime('%Y%m%d%H%M%S%f')[:-5]
    export_subdir = export_subdir.replace(" ", "_")
    export_tmp_dir = (str(settings.EXPORT_TMP_ROOT) + "/" + export_subdir)

    if not os.path.exists(export_tmp_dir):
        os.makedirs(export_tmp_dir, exist_ok=True)

    # list files from scans dir
    dir_list = [x for x in os.listdir(scans_dir) if x != '0000']
    for dir in sorted(dir_list):

        copy_export_subdir = export_tmp_dir + "/" + dir

        if not os.path.exists(copy_export_subdir):
            os.mkdir(copy_export_subdir)

        for filename in sorted(os.listdir(scans_dir + "/" + dir)):
            # check if a marked file exist, if yes copy it, or copy original scans

            marked_file_path = pathlib.Path(marked_dir + "/" + dir + "/marked_" + filename.replace('.jpeg', '.png'))
            if os.path.exists(marked_file_path):
                shutil.copyfile(marked_file_path, copy_export_subdir + "/" + filename.replace('.jpeg', '.png'))
            else:
                shutil.copyfile(scans_dir + "/" + dir + "/" + filename, copy_export_subdir + "/" + filename)


    tmp_file_list = open(file_list_path, "w")
    print('########### scans dir: '+scans_dir)
    files = sorted(glob.glob(scans_dir + '/**/*.*', recursive=True))
    for file in files:
        marked_file_path = file.replace(scans_dir,marked_dir).rsplit('/', 1)[0]
        marked_file_path += "/marked_"+file.replace('.jpeg', '.png').split('/')[-1]
        marked_file_path = pathlib.Path(marked_file_path)
        if os.path.exists(marked_file_path):
            tmp_file_list.write(str(marked_file_path) + "\n")
        else:
            tmp_file_list.write(file + "\n")
            print('########### -- file: '+file)

    tmp_file_list.close()

    return StreamingHttpResponse(amc_automatic_datacapture_subprocess(request, exam, None, True, file_list_path=file_list_path))


@exam_permission_required(['manage'])
def open_amc_exam_pdf(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    file_path = get_amc_exam_pdf_path(exam)
    try:
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('not found')

@exam_permission_required(['manage'])
def open_amc_catalog_pdf(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    file_path = get_amc_catalog_pdf_path(exam)
    try:
        return FileResponse(open(file_path, 'rb'), content_type='application/pdf')
    except FileNotFoundError:
        raise Http404('not found')

#@login_required
@exam_permission_required(['manage'])
def view_amc_log_file(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    amc_log_file_path = get_amc_project_path(exam,False)+"/amc-compiled.log"
    f = open(amc_log_file_path, 'r', encoding='latin-1')
    file_contents = f.read()
    f.close()
    return HttpResponse(file_contents)

#@login_required
@exam_permission_required(['manage'])
def get_amc_zooms(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    copy = request.POST['copy']
    page = request.POST['page']

    zooms_data = get_copy_page_zooms(exam,copy,page)

    return HttpResponse(json.dumps(zooms_data))

#@login_required
@exam_permission_required(['manage'])
def add_unrecognized_page(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    page = request.POST['unrec_page']
    copy = request.POST['copy']
    extra = True#request.POST['extra']
    img_filename = request.POST['unrecognized_img_src']#.split('/')[-1]
    add_unrecognized_page_to_project(exam,copy,page,extra,img_filename)

    return HttpResponse(True)

#@login_required
@exam_permission_required(['manage'])
def call_amc_mark(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    update_scoring_strategy = request.POST['update_scoring_strategy']

    return StreamingHttpResponse(amc_mark_subprocess(request, exam, update_scoring_strategy))
   # result = amc_mark(exam,update_scoring_strategy)

#@login_required
@exam_permission_required(['manage'])
def call_amc_automatic_association(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    assoc_primary_key = request.POST['assoc_primary_key']

    result = amc_automatic_association(exam,assoc_primary_key)

    if not 'ERR:' in result:
        url = reverse('amc_view', kwargs={'exam_pk': exam.pk})
        return JsonResponse({'ok': True, 'redirect': url})
    else:
        return HttpResponse(result)

#@login_required
@exam_permission_required(['manage'])
def amc_update_students_file(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    students_list_csv = request.FILES['students_list_csv']
    amc_project_dir = get_amc_project_path(exam,False)
    if amc_project_dir :

        #Register tmp for checking
        FileSystemStorage(location=amc_project_dir).save('_tmp_students.csv',students_list_csv)
        tmp_file = amc_project_dir+'/_tmp_students.csv'
        check = check_students_csv_file(tmp_file)
        if check == 'ok':
            if os.path.exists(amc_project_dir+'/'+students_list_csv.name):
                os.remove(amc_project_dir+'/'+students_list_csv.name)
            os.rename(tmp_file,amc_project_dir+'/'+students_list_csv.name)
            #FileSystemStorage(location=amc_project_dir).save(students_list_csv.name, students_list_csv)
            amc_update_options_xml_by_key(exam,'listeetudiants','%PROJET/'+students_list_csv.name)
        else:
            os.remove(tmp_file)
            return HttpResponse(check)

    return HttpResponse('ok')

#@login_required
@exam_permission_required(['manage'])
def call_amc_annotate(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    single_file = request.POST['single_file']
    if single_file == '1':
        single_file = True
    else:
        single_file = False

    result = amc_annotate(exam,single_file)

    return HttpResponse(result)

#@login_required
@exam_permission_required(['manage'])
def download_annotated_pdf(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    zip_file_path = create_annotated_zip(exam)

    if zip_file_path:
        zip_file = open(zip_file_path, 'rb')
        return FileResponse(zip_file)
    else:
        return HttpResponse('ZIP file not created !')

#@login_required
@exam_permission_required(['manage'])
def call_amc_generate_results(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    result = amc_generate_results(exam)

    if not 'ERR:' in result:

        project_path = get_amc_project_path(exam, False)
        results_csv_path = project_path + "/exports/" + exam.code + "_amc_raw.csv"
        file = open(results_csv_path, 'r', encoding='utf8')
        task = import_csv_data.delay(results_csv_path, exam.pk)
        task_id = task.task_id

        url = reverse('amc_view', kwargs={'exam_pk': exam.pk, 'curr_tab': 'results-tab'})
        return redirect(f"{url}?task_id={task_id}")
    else:
        return HttpResponse(result)

#@login_required
@exam_permission_required(['manage'])
def amc_manual_association_data(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    data = get_amc_manual_association_data(exam)

    return HttpResponse(json.dumps(data))

def amc_set_manual_association(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    copy_nr = request.POST['copy_nr']
    student_id = request.POST['student_id']

    result = set_amc_manual_association(exam,copy_nr,student_id)

    return HttpResponse(result)

def amc_send_annotated_papers_data(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    data = get_amc_send_annotated_papers_data(exam)
    email_subject = get_amc_option_by_key(exam, 'email_subject')
    email_text = get_amc_option_by_key(exam, 'email_text')
    # amc_update_options_xml_by_key()

    values = {"email_subject": email_subject, "email_text": email_text,"data": data}
    return HttpResponse(json.dumps(values))

#@login_required
@require_POST
@exam_permission_required(['manage'])
def call_amc_send_annotated_papers(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    selected_students = json.loads(request.POST['selected-students'])
    email_subject = request.POST['email-subject']
    email_body = request.POST['email-body']
    email_column = request.POST['email-column']

    result = amc_send_annotated_papers(exam,selected_students,email_subject,email_body,email_column)
    return HttpResponse(json.dumps(result))

@require_POST
@exam_permission_required(['manage'])
def get_amc_scan_url(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    copy_nr = request.POST['copy']
    page_nr = request.POST['page']
    amc_project_path = get_amc_project_path(exam, False)
    scan_path = None
    if amc_project_path:

        if '.' in page_nr:
            #extra page
            scan_root = str(amc_project_path) + "/scans/extra/"
            scan_path = scan_root + copy_nr.zfill(4) + "/copy_" + copy_nr.zfill(4) + "_" + page_nr + ".jpg"

        else:

            amc_data_path = amc_project_path + "/data/"
            scan_path = select_amc_scan_path(amc_data_path,copy_nr,page_nr)

            if '%HOME' in scan_path:
                print("******** home *********** "+str(Path.home())+" **************************")
                print("********* path ********** " + scan_path + " **************************")
                app_home_path = str(settings.BASE_DIR).replace(str(Path.home()), '%HOME')
                print("********* app_home_path ********** " + app_home_path + " **************************")
                scan_path = scan_path.replace(app_home_path+'/','')

                print("********* path ********** " + scan_path + " **************************")

                #tmp local
                #scan_path = scan_path.replace("%HOME/html/eXamc/","")
                print("******************* " + scan_path + " **************************")

                #change old file path (www/html/...) to new (srv/examc/private_media/...) from amc db
                scan_path = scan_path.replace('%HOME/html/eXamc',str(settings.PRIVATE_MEDIA_ROOT))

            scan_root = str(settings.SCANS_ROOT)
            if scan_path.startswith(str(settings.MARKED_SCANS_ROOT)):
                scan_root = str(settings.MARKED_SCANS_ROOT)


        scan_path = make_token_for(os.path.relpath(scan_path, scan_root), scan_root)

            #scan_path['filepath'] = scan_path

            # scan_root = str(settings.SCANS_ROOT)
            # if scan_path.startswith(str(settings.MARKED_SCANS_ROOT).split('/')[-1]):
            #     scan_root = str(settings.MARKED_SCANS_ROOT)
            # scan_path = scan_path.split('/', 1)[1]
            #
            # print("***** path ****** " + scan_path + " ********************")
            #scan_path = make_token_for(scan_path,scan_root)

    return HttpResponse(scan_path)

