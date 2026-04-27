"""  REVIEW MODULE VIEWS
    This file contains all views used for the review module
"""

import json
import os
import sys
import zipfile
from datetime import timedelta
from decimal import Decimal
from functools import wraps, partial

from cv2.detail import strip
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.http import HttpResponse, FileResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import DetailView
from shapely.geometry import Polygon

from examc_app.decorators import exam_permission_required
from examc_app.forms import *
from examc_app.mixins import ExamPermissionAndRedirectMixin
from examc_app.models import *
from examc_app.signing import verify_and_get_path
from examc_app.tasks import import_exam_scans, generate_marked_files_zip
from examc_app.utils.amc_functions import *
from examc_app.utils.epflldap import ldap_search
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.review_functions import *

#@method_decorator(login_required(login_url='/'), name='dispatch')
class ReviewView(ExamPermissionAndRedirectMixin,DetailView):
    model = Exam
    template_name = 'review/review.html'
    pk_url_kwarg = 'exam_pk'
    perm_codenames = ['manage','review']

    def get_context_data(self, **kwargs):
        context = super(ReviewView, self).get_context_data(**kwargs)
        exam = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(exam, self.request.user.id):
            pages_groups = None
            if self.request.user.is_superuser:
                pages_groups = exam.pagesGroup.all()
            else:
                user_exam = ExamUser.objects.filter(exam=exam,user=self.request.user)
                if user_exam:
                    pages_groups = user_exam.first().pages_groups.all()

            context['user_allowed'] = True
            context['nav_url'] = "reviewView"
            context['exam_pages_group_list'] = pages_groups
            context['exam_selected'] = exam
            if exam.common_exams:
                for common_exam in exam.common_exams.all():
                    if common_exam.is_overall():
                        exam = common_exam
                        break
            context['exam'] = exam
            return context
        else:
            context['user_allowed'] = False
            context['nav_url'] = "reviewView"
            context['exam'] = exam
            return context


#@method_decorator(login_required(login_url='/'), name='dispatch')
class ReviewGroupView(ExamPermissionAndRedirectMixin,DetailView):
    """
        View for managing review group for a specific exam.

        This class-based view handles the display and management of review group settings for a particular exam. It allows
        administrators to configure page groups for the exam.

        Attributes:
            model (Exam): The model class associated with the view.
            template_name : The name of the template used for rendering the view.

        Methods:
            get_context_data: Overrides the base class method to provide additional context data for rendering the view.
            post: Handles POST requests for updating review settings.
"""
    model = Exam
    template_name = 'review/reviewGroup.html'
    pk_url_kwarg = 'exam_pk'
    perm_codenames = ['manage','review']

    def get_context_data(self, **kwargs):
        context = super(ReviewGroupView, self).get_context_data(**kwargs)

        pages_group = PagesGroup.objects.get(pk=self.kwargs.get('group_pk'))

        current_page = self.kwargs['currpage']

        grading_schemes = None
        if pages_group.use_grading_scheme:
            grading_schemes = pages_group.gradingSchemes.all()
        current_grading_scheme = self.kwargs['current_grading_scheme']
        if grading_schemes and not current_grading_scheme:
            if grading_schemes:
                current_grading_scheme = grading_schemes.first()
            else:
                current_grading_scheme = 0

        # Get scans file path dict by pages groups
        copies_pages_list = get_copies_pages_by_group(pages_group)
        if user_allowed(pages_group.exam, self.request.user.id):
            context['user_allowed'] = True
            context['nav_url'] = "reviewGroup"
            context['pages_group'] = pages_group
            context['copies_pages_list'] = copies_pages_list
            context['json_copies_pages_list'] = json.dumps(copies_pages_list)
            context['currpage'] = current_page
            context['exam_selected'] = pages_group.exam
            exam = pages_group.exam
            if exam.common_exams:
                for common_exam in exam.common_exams.all():
                    if common_exam.is_overall():
                        exam = common_exam
                        break
            context['exam'] = exam
            context['grading_schemes'] = grading_schemes
            context['current_grading_scheme'] = current_grading_scheme
            return context
        else:
            context['user_allowed'] = False
            context['nav_url'] = "reviewGroup"
            context['exam'] = pages_group.exam
            context['pages_group'] = pages_group
            return context


#@method_decorator(login_required(login_url='/'), name='dispatch')
class ReviewSettingsView(ExamPermissionAndRedirectMixin,DetailView):
    """
    View for managing review settings for a specific exam.

    This class-based view handles the display and management of review settings for a particular exam. It allows
    administrators to configure reviewers and page groups for the exam.

    Attributes:
        model (Exam): The model class associated with the view.
        template_name : The name of the template used for rendering the view.
        error_msg : Error message to display if there are any issues.

    Methods:
        get_context_data: Overrides the base class method to provide additional context data for rendering the view.
    """
    model = Exam
    template_name = 'review/settings/reviewSettings.html'
    error_msg = None
    pk_url_kwarg = 'exam_pk'
    perm_codenames = ['manage']

    def get_context_data(self, **kwargs):
        """
        Retrieves additional context data for rendering the view.

        This method overrides the base class method to include context data such as formsets and current tab.

        Returns:
            dict: A dictionary containing context data for rendering the view.
        """
        context = super(ReviewSettingsView, self).get_context_data(**kwargs)

        exam = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(exam, self.request.user.id):
            curr_tab = "groups"
            if self.kwargs.get("curr_tab") != '':
                curr_tab = self.kwargs.get("curr_tab")
            formsetReviewers = ReviewersFormSet(queryset=ExamUser.objects.filter(exam=exam,group__pk__in=[2,3,4]))


            amc_project_path = get_amc_project_path(exam,False)
            if amc_project_path:
                pagesGroups = PagesGroup.objects.filter(exam=exam)
                grading_schemes_pages_groups = PagesGroup.objects.filter(exam=exam, use_grading_scheme=True)
                questions = get_questions(get_amc_project_path(exam, True)+"/data/")
                questions_choices = [ (q['name'],q['name']) for q in questions]
                formsetPagesGroups = PagesGroupsFormSet(queryset=pagesGroups, initial=[
                    {'id': None, 'group_name': 'Select', 'nb_pages': -1}], form_kwargs={"questions_choices": questions_choices})

                summernote_media_form = GradingSchemeCheckBoxForm()  # empty instance, just for .media

                context['user_allowed'] = True
                context['nav_url'] = "reviewSettingsView"
                context['exam_reviewers_formset'] = formsetReviewers
                context['exam_pages_groups_formset'] = formsetPagesGroups
                context['curr_tab'] = curr_tab
                context['summernote_media_form'] = summernote_media_form
                context['grading_schemes_pages_groups'] = grading_schemes_pages_groups
            else:

                context['user_allowed'] = True
                context['nav_url'] = "reviewSettingsView"
                context['curr_tab'] = curr_tab

            context['exam_selected'] = exam
            if exam.common_exams:
                for common_exam in exam.common_exams.all():
                    if common_exam.is_overall():
                        exam = common_exam
                        break
            context['exam'] = exam
            return context
        else:
            context['user_allowed'] = False
            context['nav_url'] = "reviewSettingsView"
            context['exam'] = exam
            return context

    # Define method to handle POST request
    def post(self, *args, **kwargs):
        """
        Handles POST requests for updating review settings.

        This method processes the form submissions for updating reviewers and page groups for the exam.

        Returns:
            HttpResponse: A response containing the updated view or an error message.
        """
        self.object = self.get_object()
        exam = Exam.objects.get(pk=self.kwargs['exam_pk'])
        error_msg = ''

        if "submit-reviewers" in self.request.POST:
            curr_tab = "reviewers"
            formset = ReviewersFormSet(self.request.POST)
            if formset.is_valid():
                for form in formset:
                    print(form)
                    if form.is_valid() and form.cleaned_data and form.cleaned_data["user"]:
                        examReviewer = form.save(commit=False)
                        examReviewer.exam = exam
                        if "pages_groups" in form.cleaned_data:
                            examReviewer.pages_groups.set(form.cleaned_data["pages_groups"])
                            examReviewer.save()
                            form.save_m2m()
        else:
            curr_tab = "groups"
            questions = get_questions(get_amc_project_path(exam, True) + "/data/")
            questions_choices = [(q['name'], q['name']) for q in questions]
            formset = PagesGroupsFormSet(self.request.POST,form_kwargs={"questions_choices": questions_choices})
            if formset.is_valid():
                for form in formset:
                    print(form)
                    if form.is_valid() and form.cleaned_data:
                        error_msg = None
                        pagesGroup = form.save(commit=False)
                        if form.cleaned_data["nb_pages"] > -1 :
                            pagesGroup.exam = exam
                            pagesGroup.save()
            else:
                print(formset.errors)

        formsetReviewers = ReviewersFormSet(queryset=ExamUser.objects.filter(exam=exam))

        questions = get_questions(get_amc_project_path(exam, True)+"/data/")
        questions_choices = [ (q['name'],q['name']) for q in questions]
        formsetPagesGroups = PagesGroupsFormSet(queryset=PagesGroup.objects.filter(exam=exam), initial=[
            {'id': None, 'group_name': 'Select', 'nb_pages': -1}], form_kwargs={"questions_choices": questions_choices})

        grading_schemes_pages_groups = PagesGroup.objects.filter(exam=exam, use_grading_scheme=True)

        context = super(ReviewSettingsView, self).get_context_data(**kwargs)
        if user_allowed(exam, self.request.user.id):
            context['user_allowed'] = True
            context['nav_url'] = "reviewSettingsView"
            context['exam_selected'] = exam
            if exam.common_exams:
                for common_exam in exam.common_exams.all():
                    if common_exam.is_overall():
                        exam = common_exam
                        break
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formsetPagesGroups
            context['exam_reviewers_formset'] = formsetReviewers
            context['curr_tab'] = curr_tab
            context['grading_schemes_pages_groups'] = grading_schemes_pages_groups
            context['error_msg'] = error_msg
        else:
            context['user_allowed'] = False
            context['nav_url'] = "reviewSettingsView"
            context['exam_selected'] = exam
            if exam.common_exams:
                for common_exam in exam.common_exams.all():
                    if common_exam.is_overall():
                        exam = common_exam
                        break
            context['exam'] = exam
            return context

        return self.render_to_response(context=context)

# @login_required
# @menu_access_required
@exam_permission_required(['manage'])
def add_new_pages_group(request, exam_pk):
    """
        Add a new pages group for an exam.

        This view function creates a new pages group for a specific exam. It saves the new group with default values and
        redirects the user back to the review settings page.

        Args:
            request: The HTTP request object.
            pk: The primary key of the exam.

        Returns:
            HttpResponseRedirect: A redirect response to the review settings page for the specified exam.
        """
    exam = Exam.objects.get(pk=exam_pk)
    new_group = PagesGroup()
    new_group.exam = exam
    new_group.group_name = 'Select...'
    new_group.nb_pages = -1
    new_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'exam_pk': exam_pk, 'curr_tab': "groups"}))


# @login_required
# @menu_access_required
@exam_permission_required(['manage'])
def delete_pages_group(request, group_pk, exam_pk):
    """
       Delete a pages group.

       This view function deletes a pages group identified by its primary key. After, it redirects the user
       back to the review settings page.

       Args:
           request: The HTTP request object.
           pages_group_pk: The primary key of the pages group to delete.

       Returns:
           HttpResponseRedirect: A redirect response to the review settings page for the specified exam.
       """
    pages_group = PagesGroup.objects.get(pk=group_pk)
    pages_group.delete()

    return redirect(reverse('reviewSettingsView', kwargs={'exam_pk': exam_pk, 'curr_tab': "groups"}))



# @login_required
# @menu_access_required
@exam_permission_required(['manage'])
def edit_pages_group_grading_help(request,exam_pk):
    """
       Edit the grading help.

       This view function edit the grading help comment . After, it redirects the user
       back to the review settings page.

       Args:
           request: The HTTP request object.

       Returns:
           HttpResponseRedirect: A redirect response to the review settings page for the specified exam.
       """
    pages_group = PagesGroup.objects.get(pk=request.POST.get('group_pk'))
    pages_group.grading_help = request.POST['grading_help']
    pages_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'exam_pk': exam_pk, 'curr_tab': "groups"}))


# @login_required
# @menu_access_required
@exam_permission_required(['manage','review'])
def get_pages_group_grading_help(request,exam_pk):
    """
      Get the grading help.

      This view function retrieves the grading help for a pages group identified by its primary key. It returns
      the grading help as an HTTP response.

      Args:
          request: The HTTP request object containing the primary key 'pk' of the pages group.

      Returns:
          HttpResponse: An HTTP response containing the grading help for the pages group.
      """

    pages_group = PagesGroup.objects.get(pk=request.POST.get('group_pk'))
    # grading_help_group_form = ckeditorForm()
    # grading_help_group_form.initial['ckeditor_txt'] = pages_group.grading_help


    return HttpResponse(pages_group.grading_help)

# @login_required
# @menu_access_required
@exam_permission_required(['manage'])
def generate_marked_files(request, exam_pk, task_id=None):
    """
          Export all the marked files.

          This function is used to export all the marked files and will delete old folders and zips folder.

          Args:
            request: TThe HTTP request object.
            pk: The primary key of the exam.

        Returns:
            return: A rendered HTML page and the zipped folder if the user is allowed to export the file.
          """
    exam = Exam.objects.get(pk=exam_pk)

    if user_allowed(exam, request.user.id):

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

            form = ExportMarkedFilesForm(request.POST, exam=exam)

            if form.is_valid():
                task = generate_marked_files_zip.delay(exam.pk, request.POST['export_type'],request.POST['with_comments'])
                task_id = task.task_id

                form = ExportMarkedFilesForm()

                exam_selected = exam
                if exam.common_exams:
                    for common_exam in exam.common_exams.all():
                        if common_exam.is_overall():
                            exam = common_exam
                            break
                return render(request, 'review/export/export_marked_files.html', {"user_allowed": True,
                    "form": form,
                    "exam_selected": exam_selected,
                    "exam": exam,
                    "nav_url": "generate_marked_files",
                    "task_id": task_id})


                # zip_file = open(generated_marked_files_zip_path, 'rb')
                # return FileResponse(zip_file)

            else:
                logger.info("INVALID")
                logger.info(form.errors)
                return HttpResponseRedirect(request.path_info)

        # if a GET (or any other method) we'll create a blank form
        else:
            form = ExportMarkedFilesForm()
            exam_selected = exam
            if exam.common_exams:
                for common_exam in exam.common_exams.all():
                    if common_exam.is_overall():
                        exam = common_exam
                        break
            return render(request, 'review/export/export_marked_files.html', {"user_allowed": True,
                                                                              "form": form,
                                                                              "exam": exam,
                                                                                "exam_selected": exam_selected,
                                                                              "nav_url": "generate_marked_files"})
    else:
        exam_selected = exam
        if exam.common_exams:
            for common_exam in exam.common_exams.all():
                if common_exam.is_overall():
                    exam = common_exam
                    break
        return render(request, 'review/export/export_marked_files.html', {"user_allowed": False,
                                                                          "form": None,
                                                                          "exam": exam,
                                                                            "exam_selected": exam_selected,
                                                                          "nav_url": "generate_marked_files"})

#@login_required
@exam_permission_required(['manage'])
def download_marked_files(request,filename, exam_pk):
    zip_file = open(str(settings.EXPORT_TMP_ROOT)+"/"+filename, 'rb')
    return FileResponse(zip_file)

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


# ------------------------------------------------
#


#@login_required
@exam_permission_required(['manage'])
def upload_scans(request, exam_pk, task_id=None):
    """
           Handles the upload of scanned files for a specific exam.

           This function is responsible for processing the upload of scanned files for a particular exam. It receives a POST
           request containing a zip file containing scanned images, extracts the images, and imports them into the system for
           further processing.

        Args:
            request: TThe HTTP request object.
            pk: The primary key of the exam.

        Returns:
            return: A rendered HTML page displaying the upload status and any error messages.
           """

    exam = Exam.objects.get(pk=exam_pk)

    # check if amc project exists and documents are compiled. if not inform user and set field readlonly
    amc_ok = True
    amc_proj_path = get_amc_project_path(exam,False)
    if not amc_proj_path :
        amc_ok = False
    else:
        amc_update_documents_msg = get_amc_update_document_info(exam)
        amc_layout_detection_msg = get_amc_layout_detection_info(exam)
        if not amc_update_documents_msg or not amc_layout_detection_msg:
            amc_ok = False

    if request.method == 'POST':
        delete_old_data = False
        if 'delete_old_data' in request.POST.keys() and request.POST['delete_old_data'] == 'on':
            delete_old_data = True
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

        task = import_exam_scans.delay(temp_file_path, exam_pk,delete_old_data)
        task_id = task.task_id
       # message = start_upload_scans(request, exam.pk, temp_file_path)

        exam_selected = exam
        if exam.common_exams:
            for common_exam in exam.common_exams.all():
                if common_exam.is_overall():
                    exam = common_exam
                    break

        return render(request, 'review/import/upload_scans.html', {
            'exam': exam,
            'exam_selected': exam_selected,
            'files': [],
            'message': '',
            'task_id':task_id,
            'amc_ok':amc_ok,
            'nav_url':'upload_scans'
        })



    exam_selected = exam
    if exam.common_exams:
        for common_exam in exam.common_exams.all():
            if common_exam.is_overall():
                exam = common_exam
                break
    return render(request, 'review/import/upload_scans.html', {'exam': exam,'exam_selected':exam_selected,'amc_ok':amc_ok,
                                                               'files': [],'nav_url':'upload_scans'})

@exam_permission_required(['manage','review'])
def saveMarkers(request, exam_pk):
    """  Save the markers and comments for a given exam page group.
        This function saves the markers and comments provided by the user for a specific exam page group.
        Args:
            request: The HTTP request object.
        Returns:
            return: A HTTP response indicating the success of the operation.
    """
    exam = Exam.objects.get(pk=exam_pk)
    page_no = int(float(request.POST['page_no'].strip()))
    question_name = get_question_name_by_student_page(get_amc_project_path(exam, True)+"/data/",int(request.POST['copy_no']),page_no)
    pages_group = PagesGroup.objects.get(exam=exam,group_name=question_name)
    scan_markers, created = PageMarkers.objects.get_or_create(copie_no=request.POST['copy_no'],
                                                              page_no=request.POST['page_no'], pages_group=pages_group,
                                                              exam=exam)
    markers = json.loads(request.POST['markers'])
    allow_highlight_only_replace = request.POST.get('allow_highlight_only_replace') == 'true'
    allow_empty_replace = request.POST.get('allow_empty_replace') == 'true'

    def has_non_highlight_markers(marker_state):
        return any(marker.get('typeName') != 'HighlightMarker' for marker in marker_state.get('markers', []))

    def has_only_highlight_markers(marker_state):
        marker_list = marker_state.get('markers', [])
        return bool(marker_list) and all(marker.get('typeName') == 'HighlightMarker' for marker in marker_list)

    marked = False
    if markers["markers"]:
        existing_markers = None
        if scan_markers.markers:
            existing_markers = json.loads(scan_markers.markers)

        should_reject_highlight_only_overwrite = (
            existing_markers is not None
            and has_non_highlight_markers(existing_markers)
            and has_only_highlight_markers(markers)
            and not allow_highlight_only_replace
        )

        if should_reject_highlight_only_overwrite:
            markers = existing_markers
        else:
            scan_markers.markers = request.POST['markers']

        scan_markers.markers = json.dumps(markers)
        fn = request.POST['filename'].replace("/protected/?token=","").replace('%3A',':')
        fn = verify_and_get_path(fn)
        fn = str(fn).replace(str(settings.BASE_DIR),"../..")
        scan_markers.filename = fn

        scan_markers.save()

        scan_markers.correctorBoxMarked = False
        if "HighlightMarker" in scan_markers.markers:
            scan_markers.correctorBoxMarked = True
            marked = True

        scan_markers.save()

        # update page markers users entry
        page_markers_user, created = PageMarkersUser.objects.get_or_create(pageMarkers=scan_markers,user=request.user)
        page_markers_user.modified = datetime.now()
        page_markers_user.save()
    else:
        existing_markers = None
        if scan_markers.markers:
            existing_markers = json.loads(scan_markers.markers)

        should_reject_empty_delete = (
            existing_markers is not None
            and has_non_highlight_markers(existing_markers)
            and not allow_empty_replace
        )

        if should_reject_empty_delete:
            markers = existing_markers
            scan_markers.markers = json.dumps(markers)
            scan_markers.correctorBoxMarked = "HighlightMarker" in scan_markers.markers
            scan_markers.save()
            marked = scan_markers.correctorBoxMarked
        else:
            scan_markers.delete()

    return HttpResponse(marked)

@exam_permission_required(['manage','review'])
def getMarkersAndComments(request, exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    data_dict = {}

    copy_no = request.POST['copy_no']
    page_no = request.POST['page_no']

    # get img signed url
    scan_url = get_scan_url(exam, copy_no, page_no)
    data_dict["copyPageUrl"] = scan_url
    try:
        scan_markers = PageMarkers.objects.get(copie_no=copy_no, page_no=page_no,exam=exam)
        if scan_markers.markers:
            data_dict["markers"] = scan_markers.markers
            markers = json.loads(scan_markers.markers)
            data_dict["markers"] = json.dumps(markers)
        else:
            data_dict["markers"] = None
    except PageMarkers.DoesNotExist:
        data_dict["markers"] = None

    corrbox_markers = []
    if not 'x' in page_no:
        corrbox_markers = get_amc_marks_positions_data(exam,copy_no.lstrip("0"), float(page_no))

    data_dict["corrector_boxes"] = json.dumps(corrbox_markers)


    # comments
    comments = PagesGroupComment.objects.filter(pages_group=request.POST['group_id'],
                                                copy_no=request.POST['copy_no']).all()
    data_dict["comments"] = [comment.serialize(request.user.id) for comment in comments]
    data_dict["copy_pages"] = json.dumps(get_scans_list_by_copy(exam,copy_no))

    return HttpResponse(json.dumps(data_dict))


@exam_permission_required(['manage','review'])
def saveComment(request,exam_pk):
    if 'delete' in request.POST:
        PagesGroupComment.objects.get(pk=request.POST['comment_id']).delete()
    else:
        comment_data = json.loads(request.POST['comment'])
        if not comment_data['id'].startswith('c'):
            comment = PagesGroupComment.objects.get(pk=comment_data['id'])
            comment.content = comment_data['content']
            comment.modified = datetime.now()
            comment.save()
        else:
            comment = PagesGroupComment()
            comment.is_new = True
            comment.content = comment_data['content']
            comment.created = datetime.now()
            comment.user_id = request.user.id
            comment.pages_group_id = request.POST['group_id']
            comment.copy_no = request.POST['copy_no']
            if comment_data['parent']:
                comment.parent_id = int(comment_data['parent'])
            comment.save()

        print(comment)

        return HttpResponse(comment.id)
    return HttpResponse('deleted')

@exam_permission_required(['manage','review'])
def update_page_group_markers(request,exam_pk):
    if request.method == 'POST':

        exam = Exam.objects.get(pk=exam_pk)
        pages_group = PagesGroup.objects.get(pk=request.POST['pages_group_pk'])
        scan_markers, created = PageMarkers.objects.get_or_create(copie_no='CORR-BOX',
                                                                  pages_group=pages_group,
                                                                  nb_pages=pages_group.nb_pages,
                                                                  exam=exam)
        markers = json.loads(request.POST['markers'])
        if markers["markers"]:
            scan_markers.markers = request.POST['markers']
            scan_markers.filename = request.POST['filename']
            scan_markers.save()
        else:
            scan_markers.delete()

        # update page markers users entry
        page_markers_user, created = PageMarkersUser.objects.get_or_create(pageMarkers=scan_markers,
                                                                           user=request.user)
        page_markers_user.modified = datetime.now()
        page_markers_user.save()

        return HttpResponse("Markers updated successfully")
    else:
        return HttpResponse("Invalid request method", status=405)


def cleanup_expired_review_locks():
    timeout_seconds = max(1, int(getattr(settings, 'REVIEW_LOCK_TIMEOUT', settings.AUTO_LOGOUT_DELAY)))
    lock_threshold = timezone.now() - timedelta(seconds=timeout_seconds)
    ReviewLock.objects.filter(updated_at__lt=lock_threshold).delete()


@exam_permission_required(['manage','review'])
def review_student_pages_group_is_locked(request,exam_pk):
    if request.method != 'POST':
        return HttpResponse("Invalid request method", status=405)

    pages_group_id = request.POST.get('pages_group_id')
    copy_no = request.POST.get('copy_no')
    if not pages_group_id or copy_no is None:
        return HttpResponse(status=400)

    try:
        copy_no_int = int(copy_no)
    except (TypeError, ValueError):
        return HttpResponse(status=400)

    pages_group = get_object_or_404(PagesGroup, pk=pages_group_id, exam_id=exam_pk)
    student = get_object_or_404(Student, copie_no=copy_no_int, exam=pages_group.exam)

    cleanup_expired_review_locks()

    with transaction.atomic():
        lock = (
            ReviewLock.objects
            .select_related('user')
            .filter(pages_group=pages_group, student=student)
            .first()
        )

        if lock and lock.user_id != request.user.id:
            return HttpResponse(lock.user.username)

        if lock and lock.user_id == request.user.id:
            ReviewLock.objects.filter(pk=lock.pk).update(updated_at=timezone.now())
        elif not lock:
            try:
                ReviewLock.objects.create(
                    user=request.user,
                    student=student,
                    pages_group=pages_group,
                )
            except IntegrityError:
                existing_lock = (
                    ReviewLock.objects
                    .select_related('user')
                    .get(pages_group=pages_group, student=student)
                )
                if existing_lock.user_id != request.user.id:
                    return HttpResponse(existing_lock.user.username)
                ReviewLock.objects.filter(pk=existing_lock.pk).update(updated_at=timezone.now())

    # Keep only the current lock for this user.
    ReviewLock.objects.filter(user=request.user).exclude(
        pages_group=pages_group,
        student=student,
    ).delete()

    return HttpResponse('')

@exam_permission_required(['manage','review'])
def remove_review_user_locks(request,exam_pk):
    if request.method != 'POST':
        return HttpResponse("Invalid request method", status=405)

    ReviewLock.objects.filter(user=request.user).delete()
    return HttpResponse('ok')

@exam_permission_required(['manage','review'])
def get_copy_page(request,exam_pk):
    exam = Exam.objects.get(pk=exam_pk)
    copy_nr = request.POST.get('copy_no')
    page_nr = request.POST.get('page_no')

    scan_url = get_scan_url(exam, copy_nr, page_nr)

    return HttpResponse(scan_url)


############ Grading schemes settings
@exam_permission_required(['manage'])
def grading_scheme_pages_group(request, exam_pk, pages_group_id: int,current_grading_scheme_id=None):
    grading_schemes = QuestionGradingScheme.objects.filter(pages_group_id=pages_group_id, pages_group__use_grading_scheme=True)
    pages_group = PagesGroup.objects.get(pk=pages_group_id)
    if current_grading_scheme_id:
        current_grading_scheme = QuestionGradingScheme.objects.get(pk=current_grading_scheme_id)
    else:
        if grading_schemes:
            current_grading_scheme = grading_schemes[0]
        else:
            current_grading_scheme = None
    return render(
        request,
        "review/settings/_grading_scheme_pages_group.html",
        {"exam_selected":pages_group.exam,"pages_group": pages_group, "grading_schemes": grading_schemes, "current_grading_scheme": current_grading_scheme},
    )

@exam_permission_required(['manage'])
def grading_scheme_panel(request, exam_pk, grading_scheme_id: int):
    grading_scheme = QuestionGradingScheme.objects.get(pk=grading_scheme_id)

    if request.method == "POST":
        grading_scheme_form = GradingSchemeForm(request.POST, instance=grading_scheme)
        saved = grading_scheme_form.is_valid()
        if saved:
            grading_scheme_form.save()
            grading_schemes = QuestionGradingScheme.objects.filter(pages_group=grading_scheme.pages_group)
            return render(
                request,
                "review/settings/_grading_scheme_pages_group.html",
                {"exam_selected": grading_scheme.pages_group.exam, "pages_group": grading_scheme.pages_group, "grading_schemes": grading_schemes,
                 "current_grading_scheme": grading_scheme, "saved": saved},
            )
        else:
            print(grading_scheme_form.errors)
    else:
        grading_scheme_form = GradingSchemeForm(instance=grading_scheme)
        saved = False

        return render(request, "review/settings/_grading_scheme_panel.html", {"exam_selected": grading_scheme.pages_group.exam, "grading_scheme": grading_scheme, "grading_scheme_form": grading_scheme_form})

@exam_permission_required(['manage'])
def grading_scheme_checkboxes(request, exam_pk, grading_scheme_id):
    grading_scheme = QuestionGradingScheme.objects.get(pk=grading_scheme_id)
    grading_scheme_checkboxes = QuestionGradingSchemeCheckBox.objects.filter(questionGradingScheme=grading_scheme,adjustment=False).exclude(name='ZERO').order_by('position','pk')
    if request.method == "POST":
        formset = GradingSchemeCheckboxFormSet(request.POST, queryset=grading_scheme_checkboxes.all())
        saved = formset.is_valid()
        if saved:
            formset.save()
            formset = GradingSchemeCheckboxFormSet(queryset=qs)
        else:
            print(formset.errors)
    else:
        formset = GradingSchemeCheckboxFormSet(queryset=grading_scheme_checkboxes.all(), initial=[
                    {'id': None, 'name': 'new', 'points': 0}])
        saved = False

    points = QuestionGradingSchemeCheckBox.objects.filter(questionGradingScheme=grading_scheme).aggregate(points__sum=Sum('points'))['points__sum']

    return render(request, "review/settings/_grading_scheme_checkboxes.html", {"exam_selected":grading_scheme.pages_group.exam,"grading_scheme": grading_scheme, "grading_scheme_checkboxes_formset": formset, "saved": saved, "points": points})

@exam_permission_required(['manage'])
def add_new_grading_scheme_checkbox(request, exam_pk, grading_scheme_id):
    grading_scheme = QuestionGradingScheme.objects.get(pk=grading_scheme_id)
    points = QuestionGradingSchemeCheckBox.objects.filter(questionGradingScheme=grading_scheme).aggregate(points__sum=Sum('points'))['points__sum']

    QuestionGradingSchemeCheckBox.objects.create(
        questionGradingScheme=grading_scheme,
        name="NEW",
        points=0,
    )
    # Return the UPDATED partial
    grading_scheme_checkboxes = QuestionGradingSchemeCheckBox.objects.filter(questionGradingScheme=grading_scheme,adjustment=False).exclude(name='ZERO')
    formset = GradingSchemeCheckboxFormSet(queryset=grading_scheme_checkboxes.all(), initial=[{'id': None, 'name': 'new', 'points': 0}])
    saved = False

    return render(request, "review/settings/_grading_scheme_checkboxes.html", {"exam_selected": grading_scheme.pages_group.exam, "grading_scheme": grading_scheme,"grading_scheme_checkboxes_formset": formset, "saved": saved, "points": points})

@exam_permission_required(['manage'])
def delete_grading_scheme_checkbox(request, exam_pk, grading_scheme_checkbox_id):
    grading_scheme_checkbox = QuestionGradingSchemeCheckBox.objects.get(pk=grading_scheme_checkbox_id)

    grading_scheme = QuestionGradingScheme.objects.get(pk=grading_scheme_checkbox.questionGradingScheme.id)
    grading_scheme_checkbox.delete()
    points = QuestionGradingSchemeCheckBox.objects.filter(questionGradingScheme=grading_scheme).aggregate(points__sum=Sum('points'))['points__sum']
    grading_scheme_checkboxes = QuestionGradingSchemeCheckBox.objects.filter(questionGradingScheme=grading_scheme,
                                                                             adjustment=False).exclude(name='ZERO')
    formset = GradingSchemeCheckboxFormSet(queryset=grading_scheme_checkboxes.all(),
                                           initial=[{'id': None, 'name': 'new', 'points': 1}])
    saved = False

    return render(request, "review/settings/_grading_scheme_checkboxes.html",
                  {"exam_selected": grading_scheme.pages_group.exam, "grading_scheme": grading_scheme,
                   "grading_scheme_checkboxes_formset": formset, "saved": saved, "points":points})



@exam_permission_required(['manage'])
def add_new_grading_scheme(request, exam_pk, pages_group_id):
    pages_group = PagesGroup.objects.get(pk=pages_group_id)
    exam = Exam.objects.get(pk=exam_pk)
    amc_data_path = get_amc_project_path(exam, True) + "/data/"
    max_points = float(get_question_max_points(amc_data_path, pages_group.group_name, None))

    grading_scheme = QuestionGradingScheme.objects.create(
        pages_group=pages_group,
        name="NEW",
        max_points=max_points,
    )

    # create adjustment, zero checkboxes
    QuestionGradingSchemeCheckBox.objects.create(questionGradingScheme=grading_scheme, name="ADJ", description="Adjustment", points=0, adjustment=True)
    QuestionGradingSchemeCheckBox.objects.create(questionGradingScheme=grading_scheme, name="ZERO", description="Zero", points=0, adjustment=False)

    grading_schemes = QuestionGradingScheme.objects.filter(pages_group_id=pages_group_id)
    pages_group = PagesGroup.objects.get(pk=pages_group_id)
    return render(
        request,
        "review/settings/_grading_scheme_pages_group.html",
        {"exam_selected": pages_group.exam, "pages_group": pages_group, "grading_schemes": grading_schemes,
         "current_grading_scheme": grading_scheme},
    )

@exam_permission_required(['manage'])
def delete_grading_scheme(request, exam_pk, grading_scheme_id):
    grading_scheme = QuestionGradingScheme.objects.get(pk=grading_scheme_id)
    pages_group = grading_scheme.pages_group
    grading_scheme.delete()
    grading_schemes = pages_group.gradingSchemes.all()
    if grading_schemes:
        current_grading_scheme = grading_schemes[0]
    else:
        current_grading_scheme = None

    return render(request,"review/settings/_grading_scheme_pages_group.html",
        {"exam_selected": pages_group.exam, "pages_group": pages_group, "grading_schemes": grading_schemes,
         "current_grading_scheme": current_grading_scheme},
    )

########### Grading Scheme Review Group
def get_review_corr_box_index(grading_scheme, copy_nr):
    if not copy_nr or str(copy_nr) in ('0', 'None', ''):
        return -1

    pages_group = grading_scheme.pages_group
    points = float(get_question_points(grading_scheme, copy_nr))

    if points > grading_scheme.max_points:
        points = float(grading_scheme.max_points)

    if points > 0:
        exam = pages_group.exam
        amc_data_path = get_amc_project_path(exam, True) + "/data/"
        question_page = select_copy_question_page(amc_data_path, copy_nr, pages_group.group_name)
        max_points = float(get_question_max_points(amc_data_path, pages_group.group_name, copy_nr))
        amc_corr_boxes = select_marks_positions(amc_data_path, int(copy_nr), question_page, None)

        nb_boxes = len(amc_corr_boxes) / 4 - 1
        if nb_boxes <= 0 or max_points <= 0:
            return -1

        points_per_box = max_points / nb_boxes
        round_value = 1 / points_per_box
        points_rnd = round(points * round_value) / round_value
        return round(points_rnd / (max_points / nb_boxes))

    zero_checked = PagesGroupGradingSchemeCheckedBox.objects.filter(
        pages_group=pages_group,
        copy_nr=copy_nr,
        gradingSchemeCheckBox__name='ZERO'
    ).exists()
    return 0 if zero_checked else -1


@exam_permission_required(['manage','review'])
def review_grading_scheme_panel(request, exam_pk, grading_scheme_id, copy_nr):
    grading_scheme = QuestionGradingScheme.objects.get(pk=grading_scheme_id)
    used_grading_scheme = other_grading_scheme_used(grading_scheme,copy_nr)
    if used_grading_scheme:
        grading_scheme = used_grading_scheme
    points = get_question_points(grading_scheme, copy_nr)
    note_enabled = str(copy_nr) not in ('0', 'None', '')
    student_report_note = ""
    if note_enabled:
        note = PagesGroupStudentReportNote.objects.filter(
            pages_group=grading_scheme.pages_group,
            copy_nr=copy_nr,
        ).first()
        if note:
            student_report_note = note.content

    resp = render(
        request,
        "review/_review_grading_scheme_panel.html",
        {
            "exam_selected": grading_scheme.pages_group.exam,
            "grading_scheme": grading_scheme,
            "copy_nr": copy_nr,
            "points": points,
            "current_grading_scheme": grading_scheme,
            "student_report_note": student_report_note,
            "student_report_note_enabled": note_enabled,
        },
    )
    # Tell the client which scheme is actually in effect and points:
    resp["X-Used-Grading-Scheme-Id"] = str(grading_scheme.id)
    resp["X-Points"] = str(points)
    resp["X-Corr-Box-Index"] = str(get_review_corr_box_index(grading_scheme, copy_nr))
    return resp

@exam_permission_required(['manage','review'])
def review_grading_scheme_checkboxes(request, exam_pk, grading_scheme_id, copy_nr):
    grading_scheme_checkboxes = get_grading_scheme_checkboxes(grading_scheme_id, copy_nr)
    grading_scheme = QuestionGradingScheme.objects.get(pk=grading_scheme_id)
    note_enabled = str(copy_nr) not in ('0', 'None', '')
    student_report_note = ""
    if note_enabled:
        note = PagesGroupStudentReportNote.objects.filter(
            pages_group=grading_scheme.pages_group,
            copy_nr=copy_nr,
        ).first()
        if note:
            student_report_note = note.content

    return render(
        request,
        "review/_review_grading_scheme_checkboxes.html",
        {
            "exam_selected": grading_scheme.pages_group.exam,
            "grading_scheme": grading_scheme,
            "grading_scheme_checkboxes": grading_scheme_checkboxes,
            "student_report_note": student_report_note,
            "student_report_note_enabled": note_enabled,
        },
    )

@exam_permission_required(['manage','review'])
def save_pages_group_student_report_note(request, exam_pk):
    pages_group_id = request.POST.get('pages_group_id')
    copy_nr = request.POST.get('copy_nr')
    content = request.POST.get('content', '')

    if not pages_group_id or str(copy_nr) in ('', 'None', '0'):
        return HttpResponse(status=400)

    pages_group = get_object_or_404(PagesGroup, pk=int(pages_group_id), exam_id=exam_pk)
    note = content.strip()
    if note == '':
        PagesGroupStudentReportNote.objects.filter(
            pages_group=pages_group,
            copy_nr=copy_nr,
        ).delete()
    else:
        student_report_note, _ = PagesGroupStudentReportNote.objects.get_or_create(
            pages_group=pages_group,
            copy_nr=copy_nr,
        )
        student_report_note.content = content
        student_report_note.user = request.user
        student_report_note.save()

    return HttpResponse('ok')

@exam_permission_required(['manage','review'])
def update_pages_group_check_box(request,exam_pk):
    copy_nr = request.POST.get('copy_nr')
    item_id_str = request.POST.get('item_id')
    checked = request.POST.get('checked') == 'true'
    pages_group = PagesGroup.objects.get(pk=int(request.POST.get('pages_group_id')))
    adjustment = request.POST.get('adjustment')
    zero = request.POST.get('zero') == 'true'
    full = request.POST.get('full') == 'true'
    if adjustment == '':
        adjustment = 0
    grading_scheme = QuestionGradingScheme.objects.get(pk=int(request.POST.get('grading_scheme_id')))
    points_rnd = ''

    if (zero and checked) or full:
        PagesGroupGradingSchemeCheckedBox.objects.filter(pages_group=pages_group, copy_nr=copy_nr).all().delete()

    points_before = float(get_question_points(grading_scheme, copy_nr))

    item_id_split = item_id_str.split("-")
    item_id = item_id_split[2]
    ref = item_id_split[1]
    if checked:
        # if adjustment != '':
        if full:
            grading_scheme_checkboxes = QuestionGradingSchemeCheckBox.objects.filter(questionGradingScheme=grading_scheme).exclude(name__in=('ZERO','ADJ'))
            for gsc in grading_scheme_checkboxes:
                if not gsc.name in ('ADJ', 'ZERO'):
                    PagesGroupGradingSchemeCheckedBox.objects.create(pages_group=pages_group,
                                                                     gradingSchemeCheckBox=gsc, copy_nr=copy_nr,adjustment=adjustment)
        else:
            if ref == "gsc":
                pggscb, create = PagesGroupGradingSchemeCheckedBox.objects.get_or_create(pages_group=pages_group, copy_nr=copy_nr,gradingSchemeCheckBox_id=item_id)
            else:
                pggscb, create = PagesGroupGradingSchemeCheckedBox.objects.get_or_create(id = item_id, pages_group=pages_group, copy_nr=copy_nr)

            pggscb.adjustment = adjustment
            pggscb.save()

        if not zero and checked:
            try:
                PagesGroupGradingSchemeCheckedBox.objects.get(pages_group=pages_group,copy_nr=copy_nr,gradingSchemeCheckBox__name='ZERO').delete()
            except PagesGroupGradingSchemeCheckedBox.DoesNotExist:
                pass
    else:
        try:
            if ref == "gsc":
                PagesGroupGradingSchemeCheckedBox.objects.get(pages_group=pages_group, copy_nr=copy_nr, gradingSchemeCheckBox_id=item_id).delete()
            else:
                if not full:
                    PagesGroupGradingSchemeCheckedBox.objects.get(id=item_id,pages_group=pages_group, copy_nr=copy_nr).delete()
        except PagesGroupGradingSchemeCheckedBox.DoesNotExist:
            pass



    points = float(get_question_points(grading_scheme, copy_nr))
    if points > grading_scheme.max_points:
        points = float(grading_scheme.max_points)
    if points == 0 or (points_before != points):
        exam = Exam.objects.get(pk=exam_pk)
        amc_data_path = get_amc_project_path(exam, True) + "/data/"
        question_page = select_copy_question_page(amc_data_path,copy_nr,pages_group.group_name)
        max_points = float(get_question_max_points(amc_data_path, pages_group.group_name, copy_nr))
        amc_corr_boxes = select_marks_positions(amc_data_path,int(copy_nr),question_page,None)


        if points > 0:
            points_per_box = max_points / (len(amc_corr_boxes) /4 - 1)
            nb_boxes = len(amc_corr_boxes) / 4 - 1
            round_value = 1/points_per_box

            points_rnd = round(points*round_value)/round_value

            box_to_check = round(points_rnd/(max_points/nb_boxes))
        else:
            points_rnd = 0
            if zero and checked:
                box_to_check = 0
            else:
                box_to_check = -1
        return HttpResponse(json.dumps([box_to_check,points_rnd,max_points]))

    return HttpResponse('')
