import base64
import json
import os
import re
import zipfile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.http import HttpResponse, FileResponse, HttpResponseRedirect
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import DetailView
from shapely.geometry import Polygon

from examc_app.forms import *
from examc_app.models import *
from examc_app.utils.amc_functions import *
from examc_app.utils.epflldap import ldap_search
from examc_app.utils.global_functions import user_allowed
from examc_app.utils.review_functions import *
from examc_app.views import menu_access_required


@method_decorator(login_required(login_url='/'), name='dispatch')
class ReviewView(DetailView):
    model = Exam
    template_name = 'review/review.html'

    def get_context_data(self, **kwargs):
        context = super(ReviewView, self).get_context_data(**kwargs)

        exam = Exam.objects.get(pk=context.get("object").id)

        if user_allowed(exam, self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "review"
            context['exam'] = exam
            context['exam_pages_group_list'] = exam.pagesGroup.all()
            return context
        else:
            context['user_allowed'] = False
            context['current_url'] = "review"
            context['exam'] = exam
            return context


@method_decorator(login_required(login_url='/'), name='dispatch')
class ReviewGroupView(DetailView):
    """
        View for managing review group for a specific exam.

        This class-based view handles the display and management of review group settings for a particular exam. It allows
        administrators to configure page groups for the exam.

        Attributes:
            model (ExamPagesGroup): The model class associated with the view.
            template_name : The name of the template used for rendering the view.

        Methods:
            get_context_data: Overrides the base class method to provide additional context data for rendering the view.
            post: Handles POST requests for updating review settings.
"""
    model = PagesGroup
    template_name = 'review/reviewGroup.html'

    def get_context_data(self, **kwargs):
        context = super(ReviewGroupView, self).get_context_data(**kwargs)

        pagesGroup = PagesGroup.objects.get(pk=context.get("object").id)

        current_page = self.kwargs['currpage']

        # Get scans file path dict by pages groups
        scans_pathes_list = get_scans_pathes_by_group(pagesGroup)
        if user_allowed(pagesGroup.exam, self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "reviewGroup"
            context['exam'] = pagesGroup.exam
            context['pages_group'] = pagesGroup
            context['scans_pathes_list'] = scans_pathes_list
            context['currpage'] = current_page,
            context['json_group_scans_pathes'] = json.dumps(scans_pathes_list)
            return context
        else:
            context['user_allowed'] = False
            context['current_url'] = "review"
            context['exam'] = pagesGroup.exam
            context['pages_group'] = pagesGroup
            return context


@method_decorator(login_required(login_url='/'), name='dispatch')
class ReviewSettingsView(DetailView):
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

    def get_context_data(self, **kwargs):
        """
        Retrieves additional context data for rendering the view.

        This method overrides the base class method to include context data such as formsets and current tab.

        Returns:
            dict: A dictionary containing context data for rendering the view.
        """
        context = super(ReviewSettingsView, self).get_context_data(**kwargs)

        exam = Exam.objects.get(pk=context.get("object").id)

        curr_tab = "groups"
        if self.kwargs.get("curr_tab") != '':
            curr_tab = self.kwargs.get("curr_tab")
        formsetPagesGroups = PagesGroupsFormSet(queryset=PagesGroup.objects.filter(exam=exam), initial=[
            {'id': None, 'group_name': '[New]', 'page_from': -1, 'page_to': -1}])
        formsetReviewers = ReviewersFormSet(queryset=Reviewer.objects.filter(exam=exam))

        grading_help_group_form = ckeditorForm()
        grading_help_group_form.initial['ckeditor_txt'] = ''

        if user_allowed(exam, self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formsetPagesGroups
            context['exam_reviewers_formset'] = formsetReviewers
            context['curr_tab'] = curr_tab
            context['gh_group_form'] = grading_help_group_form
            return context
        else:
            context['user_allowed'] = False
            context['current_url'] = "reviewSettings"
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
        exam = Exam.objects.get(pk=self.kwargs['pk'])
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
            formset = PagesGroupsFormSet(self.request.POST)
            if formset.is_valid():
                for form in formset:
                    print(form)
                    if form.is_valid() and form.cleaned_data:
                        error_msg = None
                        if form.cleaned_data["page_to"] < form.cleaned_data["page_from"]:
                            error_msg = "'PAGE TO' cannot be lower than 'PAGE FROM' !"
                            break
                        else:
                            pagesGroup = form.save(commit=False)
                            if form.cleaned_data["page_from"] > -1 and form.cleaned_data["page_to"] > -1:
                                pagesGroup.exam = exam
                                pagesGroup.save()

        formsetReviewers = ReviewersFormSet(queryset=Reviewer.objects.filter(exam=exam))
        formsetPagesGroups = PagesGroupsFormSet(queryset=PagesGroup.objects.filter(exam=exam), initial=[
            {'id': None, 'group_name': '[New]', 'page_from': -1, 'page_to': -1}])

        context = super(ReviewSettingsView, self).get_context_data(**kwargs)
        if user_allowed(exam, self.request.user.id):
            context['user_allowed'] = True
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            context['exam_pages_groups_formset'] = formsetPagesGroups
            context['exam_reviewers_formset'] = formsetReviewers
            context['curr_tab'] = curr_tab
            context['error_msg'] = error_msg
        else:
            context['user_allowed'] = False
            context['current_url'] = "reviewSettings"
            context['exam'] = exam
            return context

        return self.render_to_response(context=context)


@login_required
@menu_access_required
def add_new_pages_group(request, pk):
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
    exam = Exam.objects.get(pk=pk)
    new_group = PagesGroup()
    new_group.exam = exam
    new_group.group_name = '[NEW]'
    new_group.page_from = -1
    new_group.page_to = -1
    new_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(exam.pk), 'curr_tab': "groups"}))


@login_required
@menu_access_required
def delete_pages_group(request, pages_group_pk):
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
    pages_group = PagesGroup.objects.get(pk=pages_group_pk)
    exam_pk = pages_group.exam.pk
    pages_group.delete()

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(exam_pk), 'curr_tab': "groups"}))


@login_required
@menu_access_required
def delete_reviewer(request, reviewer_pk):
    """
    Delete a reviewer.

    This view function deletes a reviewer by its primary key. After, it redirects the user back to the review settings page.

    Args:
        request: The HTTP request object.
        reviewer_pk: The primary key of the reviewer to delete.

    Returns:
        HttpResponseRedirect: A redirect response to the review settings page for the specified exam.
    """
    reviewer = Reviewer.objects.get(pk=reviewer_pk)
    exam_pk = reviewer.exam.pk
    reviewer.delete()

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(exam_pk), 'curr_tab': "reviewers"}))


@login_required
@menu_access_required
def edit_pages_group_grading_help(request):
    """
       Edit the grading help.

       This view function edit the grading help comment . After, it redirects the user
       back to the review settings page.

       Args:
           request: The HTTP request object.

       Returns:
           HttpResponseRedirect: A redirect response to the review settings page for the specified exam.
       """
    pages_group = PagesGroup.objects.get(pk=request.POST['pk'])
    pages_group.grading_help = request.POST['grading_help']
    pages_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(pages_group.exam.pk), 'curr_tab': "groups"}))


@login_required
@menu_access_required
def get_pages_group_grading_help(request):
    """
      Get the grading help.

      This view function retrieves the grading help for a pages group identified by its primary key. It returns
      the grading help as an HTTP response.

      Args:
          request: The HTTP request object containing the primary key 'pk' of the pages group.

      Returns:
          HttpResponse: An HTTP response containing the grading help for the pages group.
      """

    pages_group = PagesGroup.objects.get(pk=request.POST['pk'])
    # grading_help_group_form = ckeditorForm()
    # grading_help_group_form.initial['ckeditor_txt'] = pages_group.grading_help


    return HttpResponse(pages_group.grading_help)


@login_required
@menu_access_required
def edit_pages_group_corrector_box(request):
    """
    Edit the corrector box of a pages group.

    This view function edits the corrector box of a pages group identified by its primary key. It receives the
    new corrector box value from the HTTP POST request and updates the pages group accordingly. After the update,
    it redirects the user back to the review settings view.

    Args:
        request: The HTTP request object containing the primary key ('pk') of the pages group
            and the new corrector box value ('corrector_box').

    Returns:
        HttpResponseRedirect: A redirection to the review settings view after the corrector box update.
    """
    pages_group = PagesGroup.objects.get(pk=request.POST['pk'])
    pages_group.correctorBoxMarked = request.POST['corrector_box']
    pages_group.save()

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(pages_group.exam.pk), 'curr_tab': "groups"}))


@login_required
@menu_access_required
def get_pages_group_rectangle_data(request):
    """
    Get rectangle data for a pages group.

    This view function retrieves rectangle data (markers) for a pages group identified by its primary key. It expects
    the group ID to be sent via an HTTP POST request. If successful, it returns JSON data containing the image path
    and the markers. If no image path is found, it returns an empty response.

    Args:
        request: The HTTP request object.

    Returns:
        HttpResponse: A JSON response containing the image path and markers, or an empty response if no image path is found.
    """
    if request.method == 'POST':
        data_dict = {}
        pagesGroup = PagesGroup.objects.get(pk=request.POST.get('group_id'))
        img_path = get_scans_path_for_group(pagesGroup)
        if img_path:
            data_dict['img_path'] = img_path
            data_dict['markers'] = pagesGroup.rectangle
            return HttpResponse(json.dumps(data_dict))
        else:
            return HttpResponse(img_path)


@login_required
@menu_access_required
def ldap_search_by_email(request):
    """
    Search in LDAP by email.

    This function is used to search a new reviewer in the ldap database. The email of the reviewer will
    give the complete name of the user and his email.

    Args:
        request: The HTTP request object containing the email address ('email') and the exam ID ('pk').

    Returns:
        HttpResponse: A response string containing user information or an indication of existence.
    """
    email = request.POST['email']
    user = Reviewer.objects.filter(user__email=email, exam__id=request.POST['pk']).all()
    if user:
        return HttpResponse("exist")

    django_user = User.objects.filter(email=email).first()
    if django_user:
        entry_str = f"{django_user.username};{django_user.first_name};{django_user.last_name};{email}"
        return HttpResponse(entry_str)

    user_entry = ldap_search.get_entry(email, 'mail')
    entry_str = user_entry['uniqueidentifier'][0] + ";" + user_entry['givenName'][0] + ";" + user_entry['sn'][
        0] + ";" + email

    return HttpResponse(entry_str)


@login_required
@menu_access_required
def add_new_reviewers(request):
    """
           Add new reviewers to review group.

           This function is used to add a new reviewers to review group and add to a specific question. After adding reviewers,
            it redirects the user back to the review settings view.

           :param request: The HTTP request object.
           :return: A rendered HTML page displaying the new reviewer.

               Args:
                    request: The HTTP request object.

                Returns:
                    return: A rendered HTML page displaying the new reviewer.
           """
    exam = Exam.objects.get(pk=request.POST.get('pk'))
    reviewers = request.POST.getlist('reviewer_list[]')
    reviewer_group, created = Group.objects.get_or_create(name='reviewer')
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
        user.groups.add(reviewer_group)
        user.save()

        examReviewer = Reviewer()
        examReviewer.user = user
        examReviewer.exam = exam
        examReviewer.save()
        examReviewer.pages_groups.set(exam.pagesGroup.all())
        examReviewer.save()
        print(examReviewer)

    return redirect(reverse('reviewSettingsView', kwargs={'pk': str(exam.pk), 'curr_tab': "reviewers"}))


@login_required
@menu_access_required
def export_marked_files(request, pk):
    """
          Export all the marked files.

          This function is used to export all the marked files and will delete old folders and zips folder.

          Args:
            request: TThe HTTP request object.
            pk: The primary key of the exam.

        Returns:
            return: A rendered HTML page and the zipped folder if the user is allowed to export the file.
          """
    exam = Exam.objects.get(pk=pk)

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
            return render(request, 'review/export/export_marked_files.html', {"user_allowed": True,
                                                                              "form": form,
                                                                              "exam": exam,
                                                                              "current_url": "export_marked_files"})
    else:
        return render(request, 'review/export/export_marked_files.html', {"user_allowed": False,
                                                                          "form": None,
                                                                          "exam": exam,
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


# ------------------------------------------------

def home(request):
    user_info = request.user.__dict__
    user_info.update(request.user.__dict__)
    return render(request, 'home.html', {
        'user': request.user,
        'user_info': user_info,
    })


@login_required
def select_exam(request, pk, current_url=None):
    url_string = '../'
    if current_url is None:
        return HttpResponseRedirect(reverse('examInfo', kwargs={'pk': str(pk)}))
    else:
        return HttpResponseRedirect(reverse(current_url, kwargs={'pk': str(pk)}))


@login_required
def upload_scans(request, pk):
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

        return render(request, 'review/import/upload_scans.html', {
            'exam': exam,
            'files': [],
            'message': message
        })

    return render(request, 'review/import/upload_scans.html', {'exam': exam,
                                                               'files': []})


@login_required
def start_upload_scans(request, pk, zip_file_path):
    """
    Extracts and imports scanned files for an exam upload.

    This function is responsible for extracting scanned files from a zip archive and importing them into the system
    for a specific exam upload process.

    Args:
        request: TThe HTTP request object.
        pk: The primary key of the exam.
        zip_file_path: The file path of the zip archive containing the scanned files.

    Returns:
        return: A message indicating the success or failure of the upload process.
    """
    exam = Exam.objects.get(pk=pk)

    zip_path = str(settings.AUTOUPLOAD_ROOT) + "/" + str(exam.year.code) + "_" + str(exam.semester.code) + "_" + exam.code
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


@login_required
def saveMarkers(request):
    """
           Save the markers and comments for a given exam page group.

           This function saves the markers and comments provided by the user for a specific exam page group.

        Args:
            request: The HTTP request object.

        Returns:
            return: A HTTP response indicating the success of the operation.
           """
    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    pages_group = PagesGroup.objects.get(pk=request.POST['reviewGroup_pk'])
    scan_markers, created = PageMarkers.objects.get_or_create(copie_no=request.POST['copy_no'],
                                                              page_no=request.POST['page_no'], pages_group=pages_group,
                                                              exam=exam)
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

            marked_img_path = str(settings.MARKED_SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(
                exam.semester.code) + "/" + exam.code + "/" + scan_markers.copie_no + "/" + "marked_" + \
                              scan_markers.filename.rsplit("/", 1)[-1].replace('.jpeg', '.png')
            os.makedirs(os.path.dirname(marked_img_path), exist_ok=True)

            with open(marked_img_path, "wb") as marked_file:
                marked_file.write(ImageData)

        scan_markers.save()
    else:
        marked_img_path = str(settings.MARKED_SCANS_ROOT) + "/" + str(exam.year.code) + "/" + str(
            exam.semester.code) + "/" + exam.code + "/" + scan_markers.copie_no + "/" + "marked_" + \
                          scan_markers.filename.rsplit("/", 1)[-1].replace('.jpeg', '.png')
        #os.remove(marked_img_path)
        scan_markers.delete()

    scan_markers.save()
    return HttpResponseRedirect(
        reverse('reviewGroup', kwargs={'pk': request.POST['reviewGroup_pk'], 'currpage': scan_markers.page_no}))


@login_required
def getMarkersAndComments(request):
    exam = Exam.objects.get(pk=request.POST['exam_pk'])
    data_dict = {}
    try:
        scan_markers = PageMarkers.objects.get(copie_no=request.POST['copy_no'], page_no=request.POST['page_no'],
                                               filename=request.POST['filename'], exam=exam)
        data_dict["markers"] = scan_markers.markers
    except PageMarkers.DoesNotExist:
        json_string = None
        data_dict["markers"] = None

    # comments
    comments = PagesGroupComment.objects.filter(pages_group=request.POST['group_id'],
                                                copy_no=request.POST['copy_no']).all()
    data_dict["comments"] = [comment.serialize(request.user.id) for comment in comments]

    return HttpResponse(json.dumps(data_dict))


@login_required
def saveComment(request):
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

    return HttpResponse("ok")


# def rectangle_check(data):
#     print(data)
# rectangle = Polygon(data)
def update_page_group_markers(request):
    global response
    if request.method == 'POST':
        pages_group_pk = request.POST.get('pages_group_pk')
        markers_json = request.POST.get('markers')

        markers_data = json.loads(markers_json)
        markers = markers_data.get('markers')

        markers_with_properties = []
        for marker in markers:
            left = marker.get('left')
            top = marker.get('top')
            width = marker.get('width')
            height = marker.get('height')
            markers_with_properties.append({'left': left, 'top': top, 'width': width, 'height': height})
        print(markers_with_properties)

        points = []
        for marker in markers_with_properties:
            left = marker['left']
            top = marker['top']
            width = marker['width']
            height = marker['height']
            a = (left, top)
            b = (left + width, top)
            c = (left + width, top + height)
            d = (left, top + height)
            points.append([a, b, c, d])
        print(points)
        rectangle_coordinates = points[0]
        rectangle_polygon = Polygon(rectangle_coordinates)
        other_polygon = Polygon(points[1])

        if rectangle_polygon.intersects(other_polygon):
            response = "True"
        else:
            response = "False"

    return HttpResponse(request, response)
