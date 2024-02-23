import datetime
import operator
import sqlite3

from django.core.serializers import serialize
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View

from examreview_app.utils.functions import *
from .forms import *
from django_tables2 import SingleTableView
from django.views.generic import DetailView, ListView, TemplateView
from .tables import ExamSelectTable
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, FileResponse, HttpRequest, HttpResponseRedirect, HttpResponseForbidden,HttpResponseBadRequest
from django.urls import reverse, reverse_lazy
import zipfile
import os
import json
from PIL import Image
from examreview_app.utils.epflldap import ldap_search
import re
import base64

# TESTING
# ------------------------------------------
#def test_function(request):
#    split_scans_by_copy('2023','1','PREPA-004')
#    return render(request, 'home.html')

# CLASSES
# ------------------------------------------

# VIEWS
# ------------------------------------------
@method_decorator(login_required, name='dispatch')
class ExamSelectView(SingleTableView):
    model = Exam
    template_name = 'exam/exam_select.html'
    table_class = ExamSelectTable
    table_pagination = False

    def get_queryset(self):
        qs = Exam.objects.all()
        if not self.request.user.is_superuser:
            qs = qs.filter(users__id=self.request.user.id)
        return qs

@method_decorator(login_required, name='dispatch')
class ExamInfoView(DetailView):
    model = Exam
    template_name = 'exam/exam_info.html'

    def get_context_data(self, **kwargs):
        context = super(ExamInfoView, self).get_context_data(**kwargs)

        global EXAM
        EXAM = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(EXAM,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = get_common_list(EXAM)
            context['current_url'] = "examInfo"
            context['exam'] = EXAM
            return context
        else:
            context['user_allowed'] = False
            return context

@method_decorator(login_required, name='dispatch')
class ReviewView(DetailView):
    model = Exam
    template_name = 'review/review.html'

    def get_context_data(self, **kwargs):
        context = super(ReviewView, self).get_context_data(**kwargs)

        exam = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(exam,self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "review"
            context['exam'] = exam
            context['exam_pages_group_list'] = exam.examPagesGroup.all()
            return context
        else:
            context['user_allowed'] = False
            context['current_url'] = "review"
            context['exam'] = exam
            return context

@method_decorator(login_required, name='dispatch')
class ReviewGroupView(DetailView):
    model = ExamPagesGroup
    template_name = 'review/reviewGroup.html'

    def get_context_data(self, **kwargs):
        context = super(ReviewGroupView, self).get_context_data(**kwargs)

        examPagesGroup = ExamPagesGroup.objects.get(pk=context.get("object").id)

        current_page = self.kwargs['currpage']

        # Get scans file path dict by pages groups
        scans_pathes_list = get_scans_pathes_by_group(examPagesGroup)
        if user_allowed(examPagesGroup.exam,self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "reviewGroup"
            context['exam'] = examPagesGroup.exam
            context['pages_group'] = examPagesGroup
            context['scans_pathes_list'] = scans_pathes_list
            context['currpage'] = current_page,
            context['json_group_scans_pathes'] = json.dumps(scans_pathes_list)
            return context
        else:
            context['user_allowed'] = False
            context['current_url'] = "review"
            context['exam'] = examPagesGroup.exam
            context['pages_group'] = examPagesGroup
            return context

@method_decorator(login_required, name='dispatch')
class ReviewSettingsView(DetailView):
    model = Exam
    template_name = 'review/reviewSettings.html'

    def get_context_data(self, **kwargs):
        context = super(ReviewSettingsView, self).get_context_data(**kwargs)

        exam = Exam.objects.get(pk=context.get("object").id)

        curr_tab = "groups"
        if "curr_tab" != '' in context:
            curr_tab = context.get("curr_tab")
        formsetPagesGroups = ExamPagesGroupsFormSet(queryset=ExamPagesGroup.objects.filter(exam=exam),initial=[{'id':None,'group_name':'[New]','page_from':-1,'page_to':-1}])
        formsetReviewers = ExamReviewersFormSet(queryset=ExamReviewer.objects.filter(exam=exam))

        if user_allowed(exam,self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formsetPagesGroups
            context['exam_reviewers_formset'] = formsetReviewers
            context['curr_tab'] = curr_tab
            return context
        else:
            context['user_allowed'] = False
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            return context

    # Define method to handle POST request
    def post(self, *args, **kwargs):
        self.object = self.get_object()
        exam = Exam.objects.get(pk=self.kwargs['pk'])

        if "submit-reviewers" in self.request.POST:
            curr_tab = "reviewers"
            formset = ExamReviewersFormSet(self.request.POST)
            if formset.is_valid():
                for form in formset:
                    print(form)
                    if form.is_valid() and form.cleaned_data and form.cleaned_data["user"]:
                        examReviewer = form.save(commit=False)
                        examReviewer.exam = exam
                        if "pages_groups" in form.cleaned_data:
                            examReviewer.pages_groups.set(form.cleaned_data["pages_groups"])
                        if form.cleaned_data["DELETE"]:
                            examReviewer.delete()
                        else:
                            examReviewer.save()
                            form.save_m2m()
        else:
            curr_tab = "groups"
            formset = ExamPagesGroupsFormSet(self.request.POST)
            if formset.is_valid():
                for form in formset:
                    print(form)
                    if form.is_valid() and form.cleaned_data :
                        pagesGroup = form.save(commit=False)
                        if form.cleaned_data["page_from"] > -1 and form.cleaned_data["page_to"] > -1:
                            pagesGroup.exam = exam
                            pagesGroup.save()
                        if form.cleaned_data["DELETE"]:
                            pagesGroup.delete()

        formsetGroups = ExamPagesGroupsFormSet(queryset=ExamPagesGroup.objects.filter(exam=exam))
        formsetReviewers = ExamReviewersFormSet(queryset=ExamReviewer.objects.filter(exam=exam))

        context = super(ReviewSettingsView, self).get_context_data(**kwargs)
        if user_allowed(exam, self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formsetGroups
            context['exam_reviewers_formset'] = formsetReviewers
            context['curr_tab'] = curr_tab
        else:
            context['user_allowed'] = False
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            return context

        return self.render_to_response(context=context)


@login_required
def add_new_pages_group(request, pk):
    exam = Exam.objects.get(pk=pk)
    new_group = ExamPagesGroup()
    new_group.exam = exam
    new_group.group_name = '[NEW]'
    new_group.page_from = -1
    new_group.page_to = -1
    new_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(exam.pk), 'curr_tab': "groups"}))

@login_required
def edit_pages_group_grading_help(request):
    pages_group = ExamPagesGroup.objects.get(pk=request.POST['pk'])
    pages_group.grading_help = request.POST['grading_help']
    pages_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(pages_group.exam.pk), 'curr_tab': "groups"}))

@login_required
def get_pages_group_grading_help(request):
    pages_group = ExamPagesGroup.objects.get(pk=request.POST['pk'])
    return HttpResponse(pages_group.grading_help)

@login_required
def edit_pages_group_corrector_box(request):
    pages_group = ExamPagesGroup.objects.get(pk=request.POST['pk'])
    pages_group.correctorBoxMarked = request.POST['corrector_box']
    pages_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(pages_group.exam.pk), 'curr_tab': "groups"}))


# @login_required
# def get_pages_group_corrector_box(request):
#     scan_markers = ScanMarkers.objects.get(pk=request.POST['pk'])
#     return HttpResponse(scan_markers.correctorBoxMarked)


@login_required
def ldap_search_by_email(request):
    email = request.POST['email']
    user = ExamReviewer.objects.filter(user__email=email, exam__id=request.POST['pk']).all()
    if user:
        return HttpResponse("exist")

    user_entry = ldap_search.get_entry(email, 'mail')
    entry_str = user_entry['uniqueidentifier'][0] + ";" + user_entry['givenName'][0] + ";" + user_entry['sn'][0] + ";" + email


    return HttpResponse(entry_str)


@login_required
def add_new_reviewers(request):
    exam = Exam.objects.get(pk=request.POST.get('pk'))
    reviewers = request.POST.getlist('reviewer_list[]')
    for reviewer in reviewers:
        user_list = reviewer.split(";")
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

        examReviewer = ExamReviewer()
        examReviewer.user = user
        examReviewer.exam = exam
        examReviewer.save()
        examReviewer.pages_groups.set(exam.examPagesGroup.all())
        examReviewer.save()
        print(examReviewer)

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(exam.pk),'curr_tab': "reviewers"}))


@login_required
def export_marked_files(request,pk):
    exam = Exam.objects.get(pk=pk)

    if user_allowed(exam,request.user.id):

        if request.method == 'POST':

            # delete old tmp folders and zips
            for filename in os.listdir(str(settings.EXPORT_TMP_ROOT)):
                file_path = os.path.join(str(settings.EXPORT_TMP_ROOT), filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print('Failed to delete %s. Reason: %s' % (file_path, e))

            form = ExportMarkedFilesForm(request.POST,exam=exam)

            if form.is_valid():

              generated_marked_files_zip_path = generate_marked_files_zip(exam, request.POST['export_type'])


              zip_file = open(generated_marked_files_zip_path, 'rb')
              return FileResponse(zip_file)

            else:
              logger.info("INVALID")
              logger.info(form.errors)
              return HttpResponseRedirect(request.path_info)

        # if a GET (or any other method) we'll create a blank form
        else:
          form = ExportMarkedFilesForm()
          return render(request, 'export/export_marked_files.html', {"user_allowed":True,
                                                        "form": form,
                                                        "exam" : exam,
                                                        "current_url": "export_marked_files"})
    else:
        return render(request, 'export/export_marked_files.html', {"user_allowed":False,
                                                      "form": None,
                                                      "exam" : exam,
                                                      "current_url": "export_marked_files"})




# TESTING
# ------------------------------------------
@login_required
def testing(request):
    user_info = request.user.__dict__
    if request.user.is_authenticated:
        user_info.update(request.user.__dict__)
        return render(request, 'review/testing.html', {
            'user': request.user,
            'user_info': user_info,
    })

@login_required
def home(request):
    user_info = request.user.__dict__
    if request.user.is_authenticated:
        user_info.update(request.user.__dict__)
        return render(request, 'home.html', {
            'user': request.user,
            'user_info': user_info,
    })

@login_required
def select_exam(request, pk, current_url=None):

    #request.session['exam_pk'] = Exam.objects.get(pk=pk)


    # if len(EXAM.scales_statistics.all()) == 0:
    #     generate_statistics(EXAM)

    url_string = '../'
    if current_url is None:
        return HttpResponseRedirect( reverse('examInfo', kwargs={'pk':str(pk)}))
    else:
        return HttpResponseRedirect( reverse(current_url, kwargs={'pk':str(pk)}) )

@login_required
def upload_scans(request, pk):
    exam = Exam.objects.get(pk=pk)

    if request.method == 'POST':
        if 'exams_zip_file' not in request.FILES:
            messages.error(request, "No zip file provided.")
            return redirect(f'../upload_scans/{exam.pk}')

        zip_file = request.FILES['exams_zip_file']
        file_name = f"exam_{exam.pk}.zip"
        temp_file_path = os.path.join(settings.AUTOUPLOAD_ROOT, file_name)

        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)

        with open(temp_file_path, 'wb') as temp_file:
            for chunk in zip_file.chunks():
                temp_file.write(chunk)

        message = start_upload_scans(request, exam.pk, temp_file_path)

        return render(request, 'import/upload_scans.html', {
                 'exam': exam,
                 'files': [],
                 'message': message
             })
        # messages.success(request, message)
        # return redirect(f'/exams/{exam.pk}')

    return render(request, 'import/upload_scans.html', {'exam': exam,
                                                        'files': []})
    #
    # files = []
    #
    # zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year) + "_" + str(exam.semester) + "_" + exam.code
    #
    # for file in os.listdir(zip_path):
    #     if os.path.isfile(os.path.join(zip_path,file)) and os.path.splitext(file)[1] == '.zip':
    #         files.append(file)
    #
    # return render(request, 'import/upload_scans.html', {
    #     'exam': exam,
    #     'files' : files,
    #     'message':''})

@login_required
def start_upload_scans(request, pk, zip_file_path):
    exam = Exam.objects.get(pk=pk)

    zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year) + "_" + str(exam.semester) + "_" + exam.code
    tmp_extract_path = zip_path + "/tmp_extract"

    # extract zip file in tmp dir
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        print("start extraction")
        zip_ref.extractall(tmp_extract_path)

    dirs = [entry for entry in os.listdir(tmp_extract_path) if os.path.isdir(os.path.join(tmp_extract_path, entry))]

    if dirs:
        tmp_extract_path = os.path.join(tmp_extract_path, dirs[0])

    result = import_scans(exam, tmp_extract_path)

    if isinstance(result, tuple) and len(result) == 2:
        message, files = result
    elif isinstance(result, str):
        message, files = result, []
    else:
        message, files = "An unexpected error occurred during the upload.", []

    # remove imported Files (zip + extracted)
    for filename in os.listdir(zip_path):
        file_path = os.path.join(zip_path, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print('Failed to delete %s. Reason: %s' % (file_path, e))

    return message
    # return render(request, 'import/upload_scans.html', {
    #     'exam': exam,
    #     'files': files,
    #     'message': message
    # })

def get_common_list(exam):
    common_list = []
    common_list.append(exam)
    if exam.common_exams.all():
        commons = list(exam.common_exams.all())
        common_list.extend(commons)
        common_list.sort(key=operator.attrgetter('code'))
    return common_list

@login_required
def saveMarkers(request):

    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    pages_group = ExamPagesGroup.get(pk=request.POST['reviewGroup'])
    scan_markers, created = ScanMarkers.objects.get_or_create(copie_no=request.POST['copy_no'], page_no=request.POST['page_no'], pages_group=pages_group, exam=exam)
    #scan_markers.pages_group = ExamPagesGroup.query.filters(exam=exam, page_from__gte=page_no)
    dataUrlPattern = re.compile('data:image/(png|jpeg);base64,(.*)$')
    ImageData = request.POST.get('marked_img_dataUrl')
    markers = json.loads(request.POST['markers'])
    if markers["markers"]:
        scan_markers.markers = request.POST['markers']
        scan_markers.comment = request.POST['comment']
        scan_markers.filename = request.POST['filename']
        if dataUrlPattern.match(ImageData):
          ImageData = dataUrlPattern.match(ImageData).group(2)
          # Decode the 64 bit string into 32 bit
          ImageData = base64.b64decode(ImageData)

          marked_img_path = str(settings.MARKED_SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code+"/"+scan_markers.copie_no+"/"+"marked_"+scan_markers.filename.rsplit("/", 1)[-1].replace('.jpeg','.png')
          os.makedirs(os.path.dirname(marked_img_path), exist_ok=True)

          with open(marked_img_path,"wb") as marked_file:
            marked_file.write(ImageData)

        scan_markers.save()
    else:
        marked_img_path = str(settings.MARKED_SCANS_ROOT) + "/" + str(exam.year) + "/" + str(exam.semester) + "/" + exam.code + "/" + scan_markers.copie_no + "/" + "marked_" + scan_markers.filename.rsplit("/", 1)[-1].replace('.jpeg', '.png')
        #os.remove(marked_img_path)
        scan_markers.delete()


    scan_markers.save()
    return HttpResponseRedirect(reverse('reviewGroup', kwargs={'pk':request.POST['reviewGroup_pk'],'currpage':scan_markers.page_no}))

@login_required
def getMarkersAndComments(request):
    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    data_dict = {}
    try:
        scan_markers = ScanMarkers.objects.get(copie_no=request.POST['copy_no'], page_no=request.POST['page_no'], filename=request.POST['filename'],exam=exam)
        data_dict["markers"]=scan_markers.markers
    except ScanMarkers.DoesNotExist:
        json_string = None
        data_dict["markers"]=None

    # comments
    comments = ExamPagesGroupComment.objects.filter(pages_group=request.POST['group_id'], copy_no=request.POST['copy_no']).all()
    data_dict["comments"] = [comment.serialize(request.user.id) for comment in comments]

    return HttpResponse(json.dumps(data_dict))

@login_required
def saveComment(request):
    comment_data = json.loads(request.POST['comment'])
    if not comment_data['id'].startswith('c') :
        comment = ExamPagesGroupComment.objects.get(pk=comment_data['id'])
        comment.content = comment_data['content']
        comment.modified = datetime.datetime.now()
        comment.save()
    else:
        comment = ExamPagesGroupComment()
        comment.is_new=True
        comment.content = comment_data['content']
        comment.created = datetime.datetime.now()
        comment.user_id = request.user.id
        comment.pages_group_id = request.POST['group_id']
        comment.copy_no = request.POST['copy_no']
        if comment_data['parent']:
            comment.parent_id = int(comment_data['parent'])
        comment.save()


    print(comment)

    return HttpResponse("ok")









##########################################
# TESTING
##########################################
@login_required
def amc_check_detection(request, pk):
    exam = Exam.objects.get(pk=pk)

    con = sqlite3.connect("/home/ludo/CEPRO/Workspace/GITHUB_KedroX/ExamReview/examreview/amc_projects/2024/1/CS-119h_final/data/capture.sqlite")
    cur = con.cursor()
    select_amc_pages_str = ("SELECT "
                            "   student as copy,"
                            "   page as page, "
                            "   mse as mse, "
                            "   REPLACE(src,'%PROJET','"+str(settings.AMC_PROJECTS_URL)+"2024/1/CS-119h_final') as source, "
                            "   (SELECT 10*(0.007 - MIN(ABS(1.0 * cz.black / cz.total - 0.007))) / 0.007 FROM capture_zone cz WHERE cz.student = cp.student AND cz.page = cp.page) as sensitivity " 
                            "FROM capture_page cp "
                            "ORDER BY copy, page")

    query = cur.execute(select_amc_pages_str)

    colname_pages = [d[0] for d in query.description]
    data_pages = [dict(zip(colname_pages, r)) for r in query.fetchall()]

    for data in data_pages:
        query = cur.execute("SELECT DISTINCT(id_a) FROM capture_zone WHERE type = 4 AND student = "+ str(data['copy']) + " AND page = " + str(data['page']))
        colname_questions_id = [d[0] for d in query.description]
        data_questions_id = [dict(zip(colname_questions_id, r)) for r in query.fetchall()]
        questions_ids=''
        for qid in data_questions_id:
            questions_ids+='%'+str(qid['id_a'])
        data['questions_ids'] = questions_ids+'%'

    cur.close()
    cur.connection.close()

    con = sqlite3.connect("/home/ludo/CEPRO/Workspace/GITHUB_KedroX/ExamReview/examreview/amc_projects/2024/1/CS-119h_final/data/layout.sqlite")
    cur = con.cursor()
    select_amc_questions_str = ("SELECT * FROM layout_question")

    query = cur.execute(select_amc_questions_str)

    colname_questions = [d[0] for d in query.description]
    data_questions = [dict(zip(colname_questions, r)) for r in query.fetchall()]

    cur.close()
    cur.connection.close()

    context = {}
    if user_allowed(exam, request.user.id):
        context['exam'] = exam
        context['user_allowed'] = True
        context['data_pages'] = data_pages
        context['data_questions'] = data_questions
    else:
        context['user_allowed'] = False

    return render(request, 'amc/amc_check_detection.html',  context)

@login_required
def get_amc_marks_positions(request):
    copy = request.POST['copy']
    page = request.POST['page']


    con = sqlite3.connect("/home/ludo/CEPRO/Workspace/GITHUB_KedroX/ExamReview/examreview/amc_projects/2024/1/CS-119h_final/data/capture.sqlite")
    cur = con.cursor()

    # Attach scoring db
    cur.execute("ATTACH DATABASE '/home/ludo/CEPRO/Workspace/GITHUB_KedroX/ExamReview/examreview/amc_projects/2024/1/CS-119h_final/data/scoring.sqlite' as scoring")

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

@login_required
def update_amc_mark_zone(request):
    zoneid = request.POST['zoneid']

    con = sqlite3.connect("/home/ludo/CEPRO/Workspace/GITHUB_KedroX/ExamReview/examreview/amc_projects/2024/1/CS-119h_final/data/capture.sqlite")
    cur = con.cursor()

    select_mark_zone_str = ("SELECT manual FROM capture_zone WHERE zoneid = " + str(zoneid))

    query = cur.execute(select_mark_zone_str)

    colname_zones = [d[0] for d in query.description]
    data_zones = [dict(zip(colname_zones, r)) for r in query.fetchall()]

    print(data_zones)

    manual = data_zones[0]
    if manual == "-1.0" or "manual == 1.0":
        manual = "0.0"
    else:
        manual = "1.0"

    update_mark_zone_str = ("UPDATE capture_zone SET manual = " + manual + " WHERE zoneid = " + str(zoneid))

    cur.execute(update_mark_zone_str)
    con.commit()

    cur.close()
    con.close()

    return HttpResponse('')

