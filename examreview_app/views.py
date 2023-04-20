from django.shortcuts import render, redirect
from examreview_app.utils.functions import *
from .forms import *
from django_tables2 import SingleTableView
from django.views.generic import DetailView, ListView, TemplateView
from .tables import ExamSelectTable
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, FileResponse, HttpRequest, HttpResponseRedirect, HttpResponseForbidden,HttpResponseBadRequest
from django.urls import reverse, reverse_lazy
import zipfile
import json

import re
import base64


# TESTING
# ------------------------------------------
#def test_function(request):
#    split_scans_by_copy('2022','1','PREPA-004')
#    return render(request, 'home.html')

# CLASSES
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
        print(scans_pathes_list)
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

        formset = ExamPagesGroupsFormSet(queryset=ExamPagesGroup.objects.filter(exam=exam))

        if user_allowed(exam,self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formset
            return context
        else:
            context['user_allowed'] = False
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formset
            return context

    # Define method to handle POST request
    def post(self, *args, **kwargs):
        exam = Exam.objects.get(pk=self.kwargs['pk'])

        formset = ExamPagesGroupsFormSet(data=self.request.POST)

        # Check if submitted forms are valid
        if formset.is_valid():
            #add, update or delete entries
            for form in formset:
                pagesGroup = form.save(commit=False)
                pagesGroup.exam = exam

                if form in formset.deleted_forms:
                    pagesGroup.delete()
                else:
                    pagesGroup.save()

        formset = ExamPagesGroupsFormSet(queryset=ExamPagesGroup.objects.filter(exam=exam))
        self.object = self.get_object()
        context = super(ReviewSettingsView, self).get_context_data(**kwargs)
        if user_allowed(exam,self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formset
        else:
            context['user_allowed'] = False
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formset
            return context
        return self.render_to_response(context=context)

# VIEWS
# ------------------------------------------


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
def upload_scans(request,pk):
    exam = Exam.objects.get(pk=pk)

    files = []

    zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year) + "_" + str(exam.semester) + "_" + exam.code
    print(zip_path)

    for file in os.listdir(zip_path):
        if os.path.isfile(os.path.join(zip_path,file)) and os.path.splitext(file)[1] == '.zip':
            files.append(file)

    return render(request, 'import/upload_scans.html', {
        'exam': exam,
        'files' : files,
        'message':''})

@login_required
def start_upload_scans(request,pk,filename):
    exam = Exam.objects.get(pk=pk)

    zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year) + "_" + str(exam.semester) + "_" + exam.code
    zip_file_path = zip_path+"/"+filename
    tmp_extract_path = zip_path+"/tmp_extract"

    # extract zip file in tmp dir
    with zipfile.ZipFile(zip_file_path, 'r') as zip_ref:
        print("start extraction")
        zip_ref.extractall(tmp_extract_path)

    # check if subfolder to get jpg files path
    first_path = tmp_extract_path+"/"+os.listdir(tmp_extract_path)[0]
    if os.path.isdir(first_path):
        tmp_extract_path = first_path

    message = import_scans(exam,tmp_extract_path)

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

    return render(request, 'import/upload_scans.html', {
        'exam': exam,
        'files' : [],
        'message':message})

def get_common_list(exam):
    common_list = []
    common_list.append(exam)
    if exam.common_exams.all():
        commons = list(exam.common_exams.all())
        common_list.extend(commons)
        common_list.sort(key=operator.attrgetter('code'))
    return common_list

@login_required
def add_new_pages_group(request,pk):
    exam = Exam.objects.get(pk=pk)
    newPG = ExamPagesGroup()
    newPG.exam = exam
    newPG.group_name = 'NEW'
    newPG.page_from = 0
    newPG.page_to = 0
    newPG.save()
    return HttpResponse(1)

@login_required
def saveMarkers(request):
    print(list(request.POST.items()))
    exam = Exam.objects.get(pk=request.POST['exam_pk'])

    scan_markers, created = ScanMarkers.objects.get_or_create(copie_no=request.POST['copy_no'], page_no=request.POST['page_no'], exam=exam)

    scan_markers.markers = request.POST['markers']
    scan_markers.comment = request.POST['comment']
    scan_markers.filename = request.POST['filename']
    print(request.POST.get('marked_img_dataUrl'))
    dataUrlPattern = re.compile('data:image/(png|jpeg);base64,(.*)$')
    ImageData = request.POST.get('marked_img_dataUrl')
    if dataUrlPattern.match(ImageData):
      ImageData = dataUrlPattern.match(ImageData).group(2)
      # Decode the 64 bit string into 32 bit
      ImageData = base64.b64decode(ImageData)

      marked_img_path = str(settings.MARKED_SCANS_ROOT)+"/"+str(exam.year)+"/"+str(exam.semester)+"/"+exam.code+"/"+scan_markers.copie_no+"/"+"marked_"+scan_markers.filename.rsplit("/", 1)[-1]
      os.makedirs(os.path.dirname(marked_img_path), exist_ok=True)

      with open(marked_img_path,"wb") as marked_file:
        marked_file.write(ImageData)

    scan_markers.save()
    print(request)
    return HttpResponseRedirect( reverse('reviewGroup', kwargs={'pk':request.POST['reviewGroup_pk'],'currpage':scan_markers.page_no}))

@login_required
def getMarkers(request):
    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    try:
        scan_markers = ScanMarkers.objects.get(copie_no=request.POST['copy_no'], page_no=request.POST['page_no'], filename=request.POST['filename'],exam=exam)
        print(scan_markers)
        json_string = scan_markers.markers
    except ScanMarkers.DoesNotExist:
        json_string = None;

    if(json_string):
        return HttpResponse(json_string)
    else:
        return HttpResponse(None)
