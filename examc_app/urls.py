from django.urls import path
from django.contrib.auth.decorators import login_required

from examc_app import views

urlpatterns = [
    # scans uplad
    path('upload_scans/<int:pk>', views.upload_scans, name="upload_scans"),
    path('start_upload_scans/<int:pk>', views.start_upload_scans, name="start_upload_scans"),
    # Review Settings
    path('reviewSettings/<int:pk>/<str:curr_tab>',login_required(views.ReviewSettingsView.as_view()), name="reviewSettingsView"),
    path('add_new_reviewers', views.add_new_reviewers, name="add_new_reviewers"),
    path('add_new_pages_group/<int:pk>',views.add_new_pages_group, name="add_new_pages_group"),
    path('edit_pages_group_grading_help', views.edit_pages_group_grading_help, name="edit_pages_group_grading_help"),
    path('get_pages_group_grading_help', views.get_pages_group_grading_help, name="get_pages_group_grading_help"),
    path('edit_pages_group_corrector_box', views.edit_pages_group_corrector_box, name="edit_pages_group_corrector_box"),
    path('get_group_path_image', views.get_group_path_image, name='get_group_path_image'),
    # EPFL ldap
    path('search_ldap', views.ldap_search_by_email, name="search_ldap"),
    # Review
    path('review/<int:pk>',login_required(views.ReviewView.as_view()), name="reviewView"),
    path('reviewGroup/<int:pk>/<int:currpage>', login_required(views.ReviewGroupView.as_view()), name="reviewGroup"),
    path('save_markers', views.saveMarkers, name="save_markers"),
    path('get_markers_and_comments', views.getMarkersAndComments, name="get_markers_and_comments"),
    path('save_comment', views.saveComment, name="save_comment"),
    # Export
    path('export_marked_files/<int:pk>', views.export_marked_files, name="export_marked_files"),
    # AMC
    path('amc_view/<int:pk>', views.amc_view, name="amc_view"),
    path('get_amc_marks_positions',views.get_amc_marks_positions, name="get_amc_marks_positions"),
    path('update_amc_mark_zone',views.update_amc_mark_zone, name="update_amc_mark_zone"),
    path('edit_amc_file',views.edit_amc_file, name="edit_amc_file"),
    path('save_amc_edited_file', views.save_amc_edited_file, name="save_amc_edited_file"),
    path('call_amc_update_documents', views.call_amc_update_documents, name="call_amc_update_documents"),
    path('call_amc_layout_detection', views.call_amc_layout_detection, name="call_amc_layout_detection"),
    path('open_amc_exam_pdf/<int:pk>', views.open_amc_exam_pdf, name="open_amc_exam_pdf"),
    path('open_amc_catalog_pdf/<int:pk>', views.open_amc_catalog_pdf, name="open_amc_catalog_pdf"),
    path('upload_amc_project/<int:pk>', views.upload_amc_project, name="upload_amc_project"),
    # testing
    path('testing', views.testing, name="testing"),
]