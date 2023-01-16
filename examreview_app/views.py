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
        print(qs)
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

        if user_allowed(EXAM,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = get_common_list(EXAM)
            context['current_url'] = "review"
            context['exam'] = EXAM
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

        if user_allowed(EXAM,self.request.user.id):
            context['user_allowed'] = True
            context['common_list'] = get_common_list(EXAM)
            context['current_url'] = "reviewSettings"
            context['exam'] = [[] for _ in range(EXAM.pages_by_copy)]
            return context
        else:
            context['user_allowed'] = False
            return context

# @method_decorator(login_required, name='dispatch')
# class ExamPagesGroupsListView(ListView):
#
#     def get_context_data(self, **kwargs):
#         context = super(ExamPagesGroupsListView, self).get_context_data(**kwargs)
#         exam = Exam.objects.get(pk=self.kwargs['pk'])
#
#         context['exam'] = exam
#         return context
#     def get_queryset(self):
#         exam = Exam.objects.get(pk=self.kwargs['pk'])
#         return ExamPagesGroup.objects.filter(exam=exam)
#
#     model = ExamPagesGroup
#     template_name = "exam/manage_exam_pages_groups.html"

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
            # first delete selected 'to delete' in form
            # for deleted_forms in formset.deleted_forms:
            #     print("DELETED")
            #     pagesGroup2Delete = deleted_forms.save(commit=False)
            #     print(pagesGroup2Delete)
            #     pagesGroup2Delete.delete()
            # then add or update other entries
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
    if request.method == 'POST':
        form = UploadScansForm(request.POST, request.FILES)
        files = request.FILES.getlist('files')
        print(form.is_valid())
        if form.is_valid():
            #exam = Exam.objects.get(pk=pk)
            print(exam)
            import_scans(exam,files)
            context = {'msg' : '<span style="color: green;">File successfully uploaded</span>'}
            return render(request, "import/uplasd_scans.html", context)
    else:
        form = UploadScansForm()
    return render(request, 'import/upload_scans.html', {
        'exam': exam})

def get_common_list(exam):
    common_list = []
    common_list.append(exam)
    if exam.common_exams.all():
        commons = list(exam.common_exams.all())
        common_list.extend(commons)
        common_list.sort(key=operator.attrgetter('code'))
    return common_list

@login_required
def manage_exam_pages_groups(request,pk):
    exam = Exam.objects.get(pk=pk)
    pagesGroups = exam.examPagesGroup.all()
    forms = []
    for pg in pagesGroups:
        forms.append(ManageExamPagesGroupsForm(instance=pg))
    return render(request, 'exam/manage_exam_pages_groups.html', {'forms': forms, 'exam':exam})

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
