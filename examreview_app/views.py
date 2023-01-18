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


# TESTING
# ------------------------------------------
def test_function(request):
    split_scans_by_copy('2022','1','PREPA-004')
    return render(request, 'home.html')

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

        global EXAM
        EXAM = Exam.objects.get(pk=context.get("object").id)

        formset = ExamPagesGroupsFormSet(queryset=ExamPagesGroup.objects.filter(exam=EXAM))
        if user_allowed(EXAM,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = get_common_list(EXAM)
            context['current_url'] = "review"
            context['exam'] = EXAM
            context['exam_pages_group_list'] = EXAM.examPagesGroup.all()
            return context
        else:
            context['user_allowed'] = False
            return context

@method_decorator(login_required, name='dispatch')
class ReviewSettingsView(DetailView):
    model = Exam
    template_name = 'review/reviewSettings.html'

    def get_context_data(self, **kwargs):
        context = super(ReviewSettingsView, self).get_context_data(**kwargs)

        global EXAM
        EXAM = Exam.objects.get(pk=context.get("object").id)

        formset = ExamPagesGroupsFormSet(queryset=ExamPagesGroup.objects.filter(exam=EXAM))

        if user_allowed(EXAM,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = get_common_list(EXAM)
            context['current_url'] = "reviewSettings"
            context['exam'] = EXAM
            context['exam_pages_groups_formset'] = formset
            return context
        else:
            context['user_allowed'] = False
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

        formset = ExamPagesGroupsFormSet(queryset=ExamPagesGroup.objects.filter(exam=EXAM))
        self.object = self.get_object()
        context = super(ReviewSettingsView, self).get_context_data(**kwargs)
        if user_allowed(EXAM,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = get_common_list(EXAM)
            context['current_url'] = "reviewSettings"
            context['exam'] = [[] for _ in range(EXAM.pages_by_copy)]
            context['exam_pages_groups_formset'] = formset
        else:
            context['user_allowed'] = False
        return self.render_to_response(context=context)

@method_decorator(login_required, name='dispatch')
class ManageExamPagesGroupsView(TemplateView):
    template_name = "exam/manage_exam_pages_groups.html"

    # Define method to handle GET request
    def get(self, *args, **kwargs):
        # Create an instance of the formset
        exam = Exam.objects.get(pk=self.kwargs['pk'])
        formset = ExamPagesGroupsFormSet(queryset=ExamPagesGroup.objects.filter(exam=exam))
        return self.render_to_response({'exam_pages_groups_formset': formset})

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
            return redirect(reverse_lazy("manageExamPagesGroups", kwargs={'pk': exam.pk}))

        return self.render_to_response({'exam_pages_groups_formset': formset})

# VIEWS
# ------------------------------------------
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

    files = [];

    zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year) + "_" + str(exam.semester) + "_" + exam.code + "_" + exam.name
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

    zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year) + "_" + str(exam.semester) + "_" + exam.code + "_" + exam.name
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

    message = "Imported 430 copies (1243545 scans)"#import_scans(exam,tmp_extract_path)

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

# @login_required
# def manage_exam_pages_groups(request,pk):
#     exam = Exam.objects.get(pk=pk)
#     pagesGroups = exam.examPagesGroup.all()
#     forms = []
#     for pg in pagesGroups:
#         forms.append(ManageExamPagesGroupsForm(instance=pg))
#     return render(request, 'exam/manage_exam_pages_groups.html', {'forms': forms, 'exam':exam})

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
