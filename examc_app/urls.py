from django.contrib.auth.decorators import login_required
from django.urls import path, include, re_path

from examc_app import views, tasks
from examc_app.admin import ExamAdmin
from examc_app.views import menu_access_required

from examc_app.views import menu_access_required, staff_status, users_view
from examc_app.views.rooms_plans_views import GenerateRoomPlanView

urlpatterns = [
    # EXAM INFO
    path('update_exam_users', views.update_exam_users, name="update_exam_users"),
    path('examInfo/<int:pk>', login_required(views.ExamInfoView.as_view(), login_url='/'), name="examInfo"),
    path('examInfo/<int:pk>/<str:task_id>', login_required(views.ExamInfoView.as_view(), login_url='/'), name="examInfo"),
    path('update_exam_options/<int:pk>', views.update_exam_options, name='update_exam_options'),
    path('create_scale/<int:pk>', login_required(views.ScaleCreateView.as_view()), name="create_scale"),
    path('delete_exam_scale/<int:scale_pk>/<int:exam_pk>', views.delete_exam_scale, name="delete_exam_scale"),
    path('set_final_scale/<int:pk>', views.set_final_scale, name="set_final_scale"),

    # PREPARATION
    path('create_exam_project', views.create_exam_project, name="create_exam_project"),
    path('exam_preparation/<int:pk>', views.exam_preparation_view,name="exam_preparation"),
    path('exam_add_section/<int:exam_pk>', views.exam_add_section,name="exam_add_section"),
    path('exam_add_section_question', views.exam_add_section_question, name="exam_add_section_question"),
    path('exam_update_section', views.exam_update_section, name="exam_update_section"),
    path('exam_update_question', views.exam_update_question, name="exam_update_question"),
    path('exam_update_answers', views.exam_update_answers, name="exam_update_answers"),
    path('exam_remove_answer',views.exam_remove_answer,name="exam_remove_answer"),
    path('exam_remove_question',views.exam_remove_question,name="exam_remove_question"),
    path('exam_remove_section',views.exam_remove_section,name="exam_remove_section"),
    path('exam_add_answer',views.exam_add_answer,name="exam_add_answer"),
    path('exam_update_first_page',views.exam_update_first_page,name="exam_update_first_page"),
    path('exam_preview_pdf/<int:exam_pk>', views.exam_preview_pdf, name="exam_preview_pdf"),
    path('get_header_section_txt', views.get_header_section_txt, name="get_header_section_txt"),

    # REVIEW SETTINGS
    path('upload_scans/<int:pk>', menu_access_required(views.upload_scans), name="upload_scans"),
    path('reviewSettings/<int:pk>/<str:curr_tab>', menu_access_required(views.ReviewSettingsView.as_view()), name="reviewSettingsView"),
    path('add_new_pages_group/<int:pk>', views.add_new_pages_group, name="add_new_pages_group"),
    path('edit_pages_group_grading_help', views.edit_pages_group_grading_help, name="edit_pages_group_grading_help"),
    path('get_pages_group_grading_help', views.get_pages_group_grading_help, name="get_pages_group_grading_help"),
    path('delete_pages_group/<int:pages_group_pk>', views.delete_pages_group, name="delete_pages_group"),

    # REVIEW
    path('review/<int:pk>', login_required(views.ReviewView.as_view()), name="reviewView"),
    path('reviewGroup/<int:pk>/<str:currpage>', login_required(views.ReviewGroupView.as_view()), name="reviewGroup"),
    path('save_markers', views.saveMarkers, name="save_markers"),
    path('get_markers_and_comments', views.getMarkersAndComments, name="get_markers_and_comments"),
    path('save_comment', views.saveComment, name="save_comment"),
    path('update_page_group_markers', views.update_page_group_markers, name="update_page_group_markers"),

    # REVIEW EXPORT
    path('generate_marked_files/<int:pk>', views.generate_marked_files, name="generate_marked_files"),
    path('download_marked_files/<str:filename>', views.download_marked_files,name="download_marked_files"),

    # AMC
    path('amc_view/<int:pk>', views.amc_view, name="amc_view"),
    path('amc_view/<int:pk>/<int:active_tab>', views.amc_view, name="amc_view"),
    path('amc_data_capture_manual/<int:pk>', views.amc_data_capture_manual, name="amc_data_capture_manual"),
    path('get_amc_marks_positions', views.get_amc_marks_positions, name="get_amc_marks_positions"),
    path('update_amc_mark_zone', views.update_amc_mark_zone, name="update_amc_mark_zone"),
    path('edit_amc_file', views.edit_amc_file, name="edit_amc_file"),
    path('save_amc_edited_file', views.save_amc_edited_file, name="save_amc_edited_file"),
    path('call_amc_update_documents', views.call_amc_update_documents, name="call_amc_update_documents"),
    path('call_amc_layout_detection', views.call_amc_layout_detection, name="call_amc_layout_detection"),
    path('call_amc_automatic_data_capture', views.call_amc_automatic_data_capture, name="call_amc_automatic_data_capture"),
    path('import_scans_from_review/<int:pk>', views.import_scans_from_review, name="import_scans_from_review"),
    path('call_amc_annotate', views.call_amc_annotate, name="call_amc_annotate"),
    path('open_amc_exam_pdf/<int:pk>', views.open_amc_exam_pdf, name="open_amc_exam_pdf"),
    path('open_amc_catalog_pdf/<int:pk>', views.open_amc_catalog_pdf, name="open_amc_catalog_pdf"),
    path('upload_amc_project/<int:pk>', views.upload_amc_project, name="upload_amc_project"),
    path('view_amc_log_file/<int:pk>', views.view_amc_log_file, name="view_amc_log_file"),
    path('get_amc_zooms', views.get_amc_zooms, name="get_amc_zooms"),
    path('add_unrecognized_page', views.add_unrecognized_page, name="add_unrecognized_page"),
    path('call_amc_mark', views.call_amc_mark, name="call_amc_mark"),
    path('call_amc_automatic_association', views.call_amc_automatic_association, name="call_amc_automatic_association"),
    path('call_amc_generate_results', views.call_amc_generate_results, name="call_amc_generate_results"),
    path('amc_update_students_file/<int:pk>', views.amc_update_students_file, name="amc_update_students_file"),
    path('download_annotated_pdf/<int:pk>', views.download_annotated_pdf, name="download_annotated_pdf"),
    path('amc_manual_association_data', views.amc_manual_association_data, name="amc_manual_association_data"),
    path('amc_set_manual_association',views.amc_set_manual_association, name="amc_set_manual_association"),
    path('amc_send_annotated_papers_data',views.amc_send_annotated_papers_data, name="amc_send_annotated_papers_data"),
    path('call_amc_send_annotated_papers/<int:pk>', views.call_amc_send_annotated_papers, name="call_amc_send_annotated_papers"),

    # RESULTS & STATISTICS
    path('catalogPdf/<int:pk>', views.display_catalog, name="catalogPdf"),
    path('catalogPdf/<int:pk>/<slug:searchFor>', views.display_catalog, name="catalogPdf"),
    path('update_question', views.update_question, name="update_question"),
    path('update_student_present/<int:pk>/<int:value>', views.update_student_present, name="update_student_present"),
    path('generateStats/<int:pk>', views.generate_stats, name="generate_stats"),
    path('generalStats/<int:pk>', views.general_statistics_view, name="generalStats"),
    path('studentsResults/<int:pk>', views.students_results_view, name="studentsResults"),
    path('questionsStats/<int:pk>', views.questions_statistics_view, name="questionsStats"),
    path('export_data/<int:pk>', views.export_data, name="export_data"),
    path('import_data_4_stats/<int:pk>', views.import_data_4_stats, name="import_data_4_stats"),
    path('upload_amc_csv/<int:pk>', views.upload_amc_csv, name="upload_amc_csv"),
    path('upload_catalog_pdf/<int:pk>', views.upload_catalog_pdf, name="upload_catalog_pdf"),

    # ROOM PLAN
    path('generate_room_plan/', GenerateRoomPlanView.as_view(), name='generate_room_plan'),

    # CSVGEN
    path('csvgen', csvgen_views.csvgen, name="csvgen"),

    # SEARCH LDAP
    path('search/', ldap_search_view.upload_excel_generate_csv, name='search_people'),

    # EPFL LDAP
    path('ldap_search_exam_user_by_email', views.ldap_search_exam_user_by_email, name="ldap_search_exam_user_by_email"),

    # CKEDITOR5
    path("ckeditor5/", include('django_ckeditor_5.urls')),

    # CELERY-PROGRESS
    path('celery-progress/', include('celery_progress.urls')),



]
