"""examreview URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from django_tequila.urls import urlpatterns as django_tequila_urlpatterns
from django.contrib.auth.decorators import login_required

from examreview_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('upload_scans/<int:pk>', views.upload_scans, name="upload_scans"),
    path('start_upload_scans/<int:pk>', views.start_upload_scans, name="start_upload_scans"),
    path('review/<int:pk>',login_required(views.ReviewView.as_view()), name="reviewView"),
    path('reviewGroup/<int:pk>/<int:currpage>', login_required(views.ReviewGroupView.as_view()), name="reviewGroup"),
    path('reviewSettings/<int:pk>/<str:curr_tab>',login_required(views.ReviewSettingsView.as_view()), name="reviewSettingsView"),
    path('examSelect', login_required(views.ExamSelectView.as_view()), name="examSelect"),
    path('examInfo/<int:pk>', login_required(views.ExamInfoView.as_view()), name="examInfo"),
    path('select_exam/<int:pk>', login_required(views.select_exam), name="select_exam"),
    path('save_markers', views.saveMarkers, name="save_markers"),
    path('get_markers_and_comments', views.getMarkersAndComments, name="get_markers_and_comments"),
    path('save_comment', views.saveComment, name="save_comment"),
    path('testing', views.testing, name="testing"),
    path('search_ldap', views.ldap_search_by_email, name="search_ldap"),
    path('add_new_reviewers', views.add_new_reviewers, name="add_new_reviewers"),
    path('add_new_pages_group/<int:pk>',views.add_new_pages_group, name="add_new_pages_group"),
    path('edit_pages_group_grading_help', views.edit_pages_group_grading_help, name="edit_pages_group_grading_help"),
    path('get_pages_group_grading_help', views.get_pages_group_grading_help, name="get_pages_group_grading_help"),
    path('edit_pages_group_corrector_box', views.edit_pages_group_corrector_box, name="edit_pages_group_corrector_box"),
    path('get_group_path_image', views.get_group_path_image, name='get_group_path_image'),
    # path('get_pages_group_corrector_box', views.get_pages_group_corrector_box, name="get_pages_group_corrector_box"),
    path('export_marked_files/<int:pk>', views.export_marked_files, name="export_marked_files"),
    path('amc_view/<int:pk>', views.amc_view, name="amc_view"),
    path('get_amc_marks_positions',views.get_amc_marks_positions, name="get_amc_marks_positions"),
    path('update_amc_mark_zone',views.update_amc_mark_zone, name="update_amc_mark_zone"),
    #path('manageExamPagesGroups/<int:pk>',login_required(views.ManageExamPagesGroupsView.as_view()), name="manageExamPagesGroups"),
    #path('test_function>', views.test_function, name="test_function")
] + static(settings.SCANS_URL, document_root=settings.SCANS_ROOT) + static(settings.AMC_PROJECTS_URL, document_root=settings.AMC_PROJECTS_ROOT)

urlpatterns += django_tequila_urlpatterns
