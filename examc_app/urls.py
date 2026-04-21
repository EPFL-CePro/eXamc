from django.contrib.auth.decorators import login_required
from django.urls import path, include, re_path

from examc_app import views, tasks

from examc_app.views.rooms_plans_views import GenerateRoomPlanView
from examc_app.views.rooms_plans_special_views import GenerateRoomPlanSpecialView

urlpatterns = [
    # EXAM INFO
    path('update_exam_users/<int:exam_pk>', views.update_exam_users, name="update_exam_users"),
    path('update_exam_info/<int:exam_pk>', views.update_exam_info, name="update_exam_info"),
    path('examInfo/<int:exam_pk>', views.ExamInfoView.as_view(), name="examInfo"),
    path('examInfo/<int:exam_pk>/<str:task_id>', views.ExamInfoView.as_view(), name="examInfo"),
    path('update_exam_options/<int:exam_pk>', views.update_exam_options, name='update_exam_options'),
    path('create_scale/<int:exam_pk>', views.ScaleCreateView.as_view(), name="create_scale"),
    path('delete_exam_scale/<int:scale_pk>/<int:exam_pk>', views.delete_exam_scale, name="delete_exam_scale"),
    path('set_final_scale/<int:scale_pk>/<int:exam_pk>/<int:all_common>', views.set_final_scale, name="set_final_scale"),
    path('validate_common_exams_settings/<int:exam_pk>',views.validate_common_exams_settings, name="validate_common_exams_settings"),
    path('set_common_exam/<int:exam_pk>', views.set_common_exam, name="set_common_exam"),

    # PREPARATION
    path('create_exam_project', views.create_exam_project, name="create_exam_project"),
    path("exam_preparation/<int:exam_pk>/", views.exam_preparation_view, name="exam_preparation"),
    path("exam_preparation/<int:exam_pk>/first-page/", views.prep_first_page_panel, name="prep_first_page_panel"),
    path("exam_preparation/<int:exam_pk>/sections/", views.prep_sections_list, name="prep_sections_list"),
    path("exam_preparation/<int:exam_pk>/sections/add/", views.add_prep_section, name="add_prep_section"),
    path("exam_preparation/<int:exam_pk>/sections/<int:section_id>/", views.prep_section_panel,name="prep_section_panel"),
    path("exam_preparation/<int:exam_pk>/sections/reorder/", views.reorder_prep_sections,name="reorder_prep_sections"),
    path("reorder_prep_questions/<int:exam_pk>/<int:section_id>", views.reorder_prep_questions, name="reorder_prep_questions"),
    path("reorder_prep_answers/<int:exam_pk>/<int:question_id>", views.reorder_prep_answers, name="reorder_prep_answers"),
    path("exam_preparation/<int:exam_pk>/sections/<int:section_id>/delete/", views.delete_prep_section,name="delete_prep_section"),
    path("exam_preparation/<int:exam_pk>/sections/<int:section_id>/questions/add/", views.add_prep_question,name="add_prep_question"),
    path("exam_preparation/<int:exam_pk>/questions/<int:question_id>/", views.prep_question_panel,name="prep_question_panel"),
    path("exam_preparation/<int:exam_pk>/questions/<int:question_id>/delete/", views.delete_prep_question,name="delete_prep_question"),
    path("exam_preparation/<int:exam_pk>/questions/<int:question_id>/answers/", views.prep_answers_block,name="prep_answers_block"),
    path("exam_preparation/<int:exam_pk>/questions/<int:question_id>/answers/add/", views.add_prep_answer,name="add_prep_answer"),
    path("exam_preparation/<int:exam_pk>/answers/<int:answer_id>/", views.prep_answer_panel, name="prep_answer_panel"),
    path("exam_preparation/<int:exam_pk>/answers/<int:answer_id>/delete/", views.delete_prep_answer,name="delete_prep_answer"),
    path("exam_preparation/<int:exam_pk>/scoring_formulas_modal/", views.scoring_formulas_modal, name="scoring_formulas_modal"),
    path("exam_preparation/<int:exam_pk>/scoring_formula/<int:pk>/delete/", views.delete_scoring_formula, name="delete_scoring_formula"),
    path("exams/<int:exam_pk>/preview/start/", views.exam_preview_start, name="exam_preview_start"),
    path("exams/<int:exam_pk>/preview/status/<int:job_pk>/", views.exam_preview_status, name="exam_preview_status"),
    path("exams/<int:exam_pk>/preview/file/<int:job_pk>/", views.exam_preview_pdf_file, name="exam_preview_pdf_file"),
    path('edit_latex_file/<int:exam_pk>', views.edit_latex_file, name="edit_latex_file"),
    path('save_latex_edited_file/<int:exam_pk>', views.save_latex_edited_file, name="save_latex_edited_file"),
    path('edit_latex_packages/<int:exam_pk>', views.edit_latex_packages, name="edit_latex_packages"),
    path('save_latex_edited_packages/<int:exam_pk>', views.save_latex_edited_packages, name="save_latex_edited_packages"),
    path('generate_final_exam_files/start/<int:exam_pk>',views.generate_final_exam_files_start,name="generate_final_exam_files_start"),
    path("unlock_exam_editing/<int:exam_pk>", views.unlock_exam_editing, name="unlock_exam_editing"),


    # REVIEW SETTINGS
    path('upload_scans/<int:exam_pk>', views.upload_scans, name="upload_scans"),
    path('reviewSettings/<int:exam_pk>/<str:curr_tab>', views.ReviewSettingsView.as_view(), name="reviewSettingsView"),
    path('add_new_pages_group/<int:exam_pk>', views.add_new_pages_group, name="add_new_pages_group"),
    path('edit_pages_group_grading_help/<int:exam_pk>', views.edit_pages_group_grading_help, name="edit_pages_group_grading_help"),
    path('get_pages_group_grading_help/<int:exam_pk>', views.get_pages_group_grading_help, name="get_pages_group_grading_help"),
    path('delete_pages_group/<int:group_pk>/<int:exam_pk>', views.delete_pages_group, name="delete_pages_group"),
    path("grading_scheme_pages_group/<int:exam_pk>/<int:pages_group_id>",views.grading_scheme_pages_group,name="grading_scheme_pages_group"),
    path("grading_scheme_pages_group/<int:exam_pk>/<int:pages_group_id>/<int:current_grading_scheme_id>",views.grading_scheme_pages_group,name="grading_scheme_pages_group"),
    path("grading_scheme_panel/<int:exam_pk>/<int:grading_scheme_id>", views.grading_scheme_panel, name="grading_scheme_panel"),
    path("grading_scheme_checkboxes/<int:exam_pk>/<int:grading_scheme_id>", views.grading_scheme_checkboxes, name="grading_scheme_checkboxes"),
    path("delete_grading_scheme_checkbox/<int:exam_pk>/<int:grading_scheme_checkbox_id>", views.delete_grading_scheme_checkbox,name="delete_grading_scheme_checkbox"),
    path("delete_grading_scheme/<int:exam_pk>/<int:grading_scheme_id>", views.delete_grading_scheme,name="delete_grading_scheme"),
    path("add_new_grading_scheme_checkbox/<int:exam_pk>/<int:grading_scheme_id>", views.add_new_grading_scheme_checkbox,name="add_new_grading_scheme_checkbox"),
    path("add_new_grading_scheme/<int:exam_pk>/<int:pages_group_id>", views.add_new_grading_scheme,name="add_new_grading_scheme"),


    # REVIEW
    path('review/<int:exam_pk>', views.ReviewView.as_view(), name="reviewView"),
    path('reviewGroup/<int:exam_pk>/<int:group_pk>/<str:currpage>/<int:current_grading_scheme>', views.ReviewGroupView.as_view(), name="reviewGroup"),
    path('save_markers/<int:exam_pk>', views.saveMarkers, name="save_markers"),
    path('get_markers_and_comments/<int:exam_pk>', views.getMarkersAndComments, name="get_markers_and_comments"),
    path('save_comment/<int:exam_pk>', views.saveComment, name="save_comment"),
    path('update_page_group_markers/<int:exam_pk>', views.update_page_group_markers, name="update_page_group_markers"),
    path('review_student_pages_group_is_locked/<int:exam_pk>', views.review_student_pages_group_is_locked, name="review_student_pages_group_is_locked"),
    path('remove_review_user_locks/<int:exam_pk>',views.remove_review_user_locks, name="remove_review_user_locks"),
    path('get_copy_page/<int:exam_pk>',views.get_copy_page,name="get_copy_page"),
    path('review_grading_scheme_panel/<int:exam_pk>/<int:grading_scheme_id>/<str:copy_nr>', views.review_grading_scheme_panel, name="review_grading_scheme_panel"),
    path('review_grading_scheme_checkboxes/<int:exam_pk>/<int:grading_scheme_id>/<str:copy_nr>', views.review_grading_scheme_checkboxes, name="review_grading_scheme_checkboxes"),
    path('update_pages_group_check_box/<int:exam_pk>',views.update_pages_group_check_box, name="update_pages_group_check_box"),

    # REVIEW EXPORT
    path('generate_marked_files/<int:exam_pk>', views.generate_marked_files, name="generate_marked_files"),
    path('download_marked_files/<str:filename>/<int:exam_pk>', views.download_marked_files,name="download_marked_files"),

    # AMC
    path('amc_view/<int:exam_pk>', views.amc_view, name="amc_view"),
    path('amc_view/<int:exam_pk>/<str:curr_tab>', views.amc_view, name="amc_view"),
    path('amc_data_capture_manual/<int:exam_pk>', views.amc_data_capture_manual, name="amc_data_capture_manual"),
    path('get_amc_marks_positions/<int:exam_pk>', views.get_amc_marks_positions, name="get_amc_marks_positions"),
    path('update_amc_mark_zone/<int:exam_pk>', views.update_amc_mark_zone, name="update_amc_mark_zone"),
    path('edit_amc_file/<int:exam_pk>', views.edit_amc_file, name="edit_amc_file"),
    path('save_amc_edited_file/<int:exam_pk>', views.save_amc_edited_file, name="save_amc_edited_file"),
    path('call_amc_update_documents/<int:exam_pk>', views.call_amc_update_documents, name="call_amc_update_documents"),
    path('call_amc_layout_detection/<int:exam_pk>', views.call_amc_layout_detection, name="call_amc_layout_detection"),
    path('call_amc_automatic_data_capture/<int:exam_pk>', views.call_amc_automatic_data_capture, name="call_amc_automatic_data_capture"),
    path('import_scans_from_review/<int:exam_pk>', views.import_scans_from_review, name="import_scans_from_review"),
    path('import_scans_from_review_pages/<int:exam_pk>', views.import_scans_from_review_pages, name="import_scans_from_review_pages"),
    path('call_amc_annotate/<int:exam_pk>', views.call_amc_annotate, name="call_amc_annotate"),
    path('amc_annotate_status/<int:exam_pk>/<str:job_id>/', views.amc_annotate_status, name='amc_annotate_status'),
    path('open_amc_exam_pdf/<int:exam_pk>', views.open_amc_exam_pdf, name="open_amc_exam_pdf"),
    path('open_amc_catalog_pdf/<int:exam_pk>', views.open_amc_catalog_pdf, name="open_amc_catalog_pdf"),
    path('upload_amc_project/<int:exam_pk>', views.upload_amc_project, name="upload_amc_project"),
    path('view_amc_log_file/<int:exam_pk>', views.view_amc_log_file, name="view_amc_log_file"),
    path('get_amc_zooms/<int:exam_pk>', views.get_amc_zooms, name="get_amc_zooms"),
    path('add_unrecognized_page/<int:exam_pk>', views.add_unrecognized_page, name="add_unrecognized_page"),
    path('call_amc_mark/<int:exam_pk>', views.call_amc_mark, name="call_amc_mark"),
    path('call_amc_automatic_association/<int:exam_pk>', views.call_amc_automatic_association, name="call_amc_automatic_association"),
    path('call_amc_generate_results/<int:exam_pk>', views.call_amc_generate_results, name="call_amc_generate_results"),
    path('amc_update_students_file/<int:exam_pk>', views.amc_update_students_file, name="amc_update_students_file"),
    path('download_annotated_pdf/<int:exam_pk>', views.download_annotated_pdf, name="download_annotated_pdf"),
    path('amc_manual_association_data/<int:exam_pk>', views.amc_manual_association_data, name="amc_manual_association_data"),
    path('amc_set_manual_association/<int:exam_pk>',views.amc_set_manual_association, name="amc_set_manual_association"),
    path('amc_send_annotated_papers_data/<int:exam_pk>',views.amc_send_annotated_papers_data, name="amc_send_annotated_papers_data"),
    path('call_amc_send_annotated_papers/<int:exam_pk>', views.call_amc_send_annotated_papers, name="call_amc_send_annotated_papers"),
    path('get_amc_scan_url/<int:exam_pk>', views.get_amc_scan_url, name="get_amc_scan_url"),
    path('get_unrecognized_pages/<int:exam_pk>', views.get_unrecognized_pages, name="get_unrecognized_pages"),

    # RESULTS & STATISTICS
    path('catalogPdf/<int:exam_pk>', views.display_catalog, name="catalogPdf"),
    path('catalogPdf/<int:exam_pk>/<slug:searchFor>', views.display_catalog, name="catalogPdf"),
    #path('update_question', views.update_question, name="update_question"),
    path('update_questions/<int:exam_pk>', views.update_questions, name="update_questions"),
    path('update_student_present/<int:exam_pk>/<int:student_pk>/<int:value>', views.update_student_present, name="update_student_present"),
    path('generateStats/<int:exam_pk>', views.generate_stats, name="generate_stats"),
    path('generalStats/<int:exam_pk>', views.general_statistics_view, name="generalStats"),
    path('studentsResults/<int:exam_pk>', views.students_results_view, name="studentsResults"),
    path('questionsStats/<int:exam_pk>', views.questions_statistics_view, name="questionsStats"),
    path('export_data/<int:exam_pk>', views.export_data, name="export_data"),
    path('import_data_4_stats/<int:exam_pk>', views.import_data_4_stats, name="import_data_4_stats"),
    path('upload_amc_csv/<int:exam_pk>', views.upload_amc_csv, name="upload_amc_csv"),
    path('upload_catalog_pdf/<int:exam_pk>', views.upload_catalog_pdf, name="upload_catalog_pdf"),

    # ROOM PLAN
    path('generate_room_plan/', GenerateRoomPlanView.as_view(), name='generate_room_plan'),
    path('generate_room_plan/special', GenerateRoomPlanSpecialView.as_view(), name='generate_room_plan_special'),

    # CSVGEN
    path('csvgen/', views.csvgen, name="csvgen"),
    # path('export_csv/', views.export_csv, name="export_csv"),
    path('import_students_excel/', views.import_students_excel, name="import_students_excel"),
    path('change_csv_type/<str:choice>', views.change_csv_type, name="change_csv_type"),

    # SEARCH LDAP
    path('search/', views.upload_excel_generate_csv, name='search_people'),

    # EPFL LDAP
    path('ldap_search_exam_user_by_email/<int:exam_pk>', views.ldap_search_exam_user_by_email, name="ldap_search_exam_user_by_email"),

    # # CKEDITOR5
    # path("ckeditor5/", include('django_ckeditor_5.urls')),

    # SUMMERNOTE
    path("summernote/", include("django_summernote.urls")),

    # CELERY-PROGRESS
    path('celery-progress/', include('celery_progress.urls')),

    #
    path('test/',views.test,name="test"),
    # path('subprocess_test/',views.subprocess_test,name="subprocess_test"),
    #


]
