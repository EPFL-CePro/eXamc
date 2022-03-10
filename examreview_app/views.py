from django.shortcuts import render
from examreview_app.utils.functions import *
from django import forms
from django_tables2 import SingleTableView
from django.views.generic import DetailView
from .tables import ExamSelectTable
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404, FileResponse, HttpRequest, HttpResponseRedirect, HttpResponseForbidden,HttpResponseBadRequest
from django.urls import reverse


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

        return context

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
    if request.method == 'POST':
        form = UploadScansForm(request.POST, request.FILES)
        files = request.FILES.getlist('files')
        print(form.is_valid())
        if form.is_valid():
            exam = Exam.objects.get(pk=pk)
            print(exam)
            import_scans(exam,files)
            context = {'msg' : '<span style="color: green;">File successfully uploaded</span>'}
            return render(request, "home.html", context)
    else:
        form = UploadScansForm()
    return render(request, 'home.html', {'form': form})
