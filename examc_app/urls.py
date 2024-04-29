from django.urls import path
from django.contrib.auth.decorators import login_required, user_passes_test

from examc_app.admin import ExamAdmin
from examc_app import views
from examc_app.views import menu_access_required, staff_status, users_view

urlpatterns = [
    path('users/', users_view, name='users'),
    path('staff-status/<int:user_id>/', staff_status, name='staff_status'),
    path('admin/exam/import/', ExamAdmin.import_csv_data),
    # scans upload
    path('upload_scans/<int:pk>', menu_access_required(views.upload_scans), name="upload_scans"),
    path('start_upload_scans/<int:pk>', views.start_upload_scans, name="start_upload_scans"),
    # Review Settings
    path('reviewSettings/<int:pk>/<str:curr_tab>',menu_access_required(views.ReviewSettingsView.as_view()) , name="reviewSettingsView"),
    path('add_new_reviewers', views.add_new_reviewers, name="add_new_reviewers"),
    path('add_new_pages_group/<int:pk>',views.add_new_pages_group, name="add_new_pages_group"),
    path('edit_pages_group_grading_help', views.edit_pages_group_grading_help, name="edit_pages_group_grading_help"),
    path('get_pages_group_grading_help', views.get_pages_group_grading_help, name="get_pages_group_grading_help"),
    path('edit_pages_group_corrector_box', views.edit_pages_group_corrector_box, name="edit_pages_group_corrector_box"),
    path('get_pages_group_rectangle_data', views.get_pages_group_rectangle_data, name='get_pages_group_rectangle_data'),
    # EPFL ldap
    path('search_ldap', views.ldap_search_by_email, name="search_ldap"),
    # Review
    path('review/<int:pk>',login_required(views.ReviewView.as_view()), name="reviewView"),
    path('reviewGroup/<int:pk>/<int:currpage>', login_required(views.ReviewGroupView.as_view()), name="reviewGroup"),
    path('save_markers', views.saveMarkers, name="save_markers"),
    path('get_markers_and_comments', views.getMarkersAndComments, name="get_markers_and_comments"),
    path('save_comment', views.saveComment, name="save_comment"),
    path('update_page_group_markers', views.update_page_group_markers, name="update_page_group_markers"),
    # Export
    path('export_marked_files/<int:pk>', views.export_marked_files, name="export_marked_files"),
    # AMC
    path('amc_view/<int:pk>', views.amc_view, name="amc_view"),
    path('amc_view/<int:pk>/<int:active_tab>', views.amc_view, name="amc_view"),
    path('amc_data_capture_manual/<int:pk>', views.amc_data_capture_manual, name="amc_data_capture_manual"),
    path('get_amc_marks_positions',views.get_amc_marks_positions, name="get_amc_marks_positions"),
    path('update_amc_mark_zone',views.update_amc_mark_zone, name="update_amc_mark_zone"),
    path('edit_amc_file',views.edit_amc_file, name="edit_amc_file"),
    path('save_amc_edited_file', views.save_amc_edited_file, name="save_amc_edited_file"),
    path('call_amc_update_documents', views.call_amc_update_documents, name="call_amc_update_documents"),
    path('call_amc_layout_detection', views.call_amc_layout_detection, name="call_amc_layout_detection"),
    path('call_amc_automatic_data_capture', views.call_amc_automatic_data_capture, name="call_amc_automatic_data_capture"),
    path('call_amc_annotate', views.call_amc_annotate, name="call_amc_annotate"),
    path('open_amc_exam_pdf/<int:pk>', views.open_amc_exam_pdf, name="open_amc_exam_pdf"),
    path('open_amc_catalog_pdf/<int:pk>', views.open_amc_catalog_pdf, name="open_amc_catalog_pdf"),
    path('upload_amc_project/<int:pk>', views.upload_amc_project, name="upload_amc_project"),
    path('view_amc_log_file/<int:pk>', views.view_amc_log_file, name="view_amc_log_file"),
    path('get_amc_zooms', views.get_amc_zooms, name="get_amc_zooms"),
    path('add_unrecognized_page', views.add_unrecognized_page, name="add_unrecognized_page"),
    path('call_amc_mark', views.call_amc_mark, name="call_amc_mark"),
    path('call_amc_automatic_association', views.call_amc_automatic_association, name="call_amc_automatic_association"),
    path('call_amc_generate_results',views.call_amc_generate_results, name="call_amc_generate_results"),
    path('amc_update_students_file/<int:pk>', views.amc_update_students_file, name="amc_update_students_file"),
    path('download_annotated_pdf/<int:pk>', views.download_annotated_pdf, name="download_annotated_pdf"),
    # Results & Statistics
    path('catalogPdf/<int:pk>',views.display_catalog, name="catalogPdf"),
    path('catalogPdf/<int:pk>/<slug:searchFor>',views.display_catalog, name="catalogPdf"),
    path('update_question', views.update_question, name="update_question"),
    path('update_student_present', views.update_student_present, name="update_student_present"),
    path('generateStats/<int:pk>', views.generate_stats, name="generate_stats"),
    path('generalStats/<int:pk>', views.general_statistics_view, name="generalStats"),
    path('studentsStats/<int:pk>', views.students_statistics_view, name="studentsStats"),
    path('questionsStats/<int:pk>', views.questions_statistics_view, name="questionsStats"),
    path('export_data/<int:pk>', views.export_data, name="export_data"),
    path('import_data_4_stats/<int:pk>', views.import_data_4_stats, name="import_data_4_stats"),
    path('upload_amc_csv/<int:pk>', views.upload_amc_csv, name="upload_amc_csv"),
    path('upload_catalog_pdf/<int:pk>', views.upload_catalog_pdf, name="upload_catalog_pdf"),
    # testing
    path('testing', views.testing, name="testing"),
]