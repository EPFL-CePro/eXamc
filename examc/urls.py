# """examc URL Configuration
#
# The `urlpatterns` list routes URLs to views. For more information please see:
#     https://docs.djangoproject.com/en/3.2/topics/http/urls/
# Examples:
# Function views
#     1. Add an import:  from my_app import views
#     2. Add a URL to urlpatterns:  path('', views.home, name='home')
# Class-based views
#     1. Add an import:  from other_app.views import Home
#     2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
# Including another URLconf
#     1. Import the include() function: from django.urls import include, path
#     2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
# """
from celery_progress.urls import app_name
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path, include
from django_tequila.urls import urlpatterns as django_tequila_urlpatterns

from examc_app import views
from examc_app.admin import ExamAdmin, CourseAdmin
from examc_app.views import staff_status, users_view

urlpatterns = ([
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),
    path('', include('examc_app.urls')),
    path('', views.home, name='home'),
    path('login_form/', views.log_in, name='login_form'),
    path('logout', views.logout,name='logout'),
    path('home',views.home, name='home'),
    path('users/', users_view, name='users'),
    path('staff-status/<int:user_id>/', staff_status, name='staff_status'),
    path('admin/exam/import_exams_data/', ExamAdmin.import_exams_csv_data),
    path('admin/course/import_courses_data/', CourseAdmin.import_courses_json_data),
    path('examSelect', login_required(views.ExamSelectView.as_view(), login_url='/'), name="examSelect"),
    path('examInfo/<int:pk>', login_required(views.ExamInfoView.as_view(), login_url='/'), name="examInfo"),
    path('update_exam_options/<int:pk>', views.update_exam_options, name='update_exam_options'),
    path('select_exam/<int:pk>', login_required(views.select_exam), name="select_exam"),
    path('getCommonExams/<int:pk>', views.getCommonExams, name="getCommonExams"),
    path('create_scale/<int:pk>', login_required(views.ScaleCreateView.as_view()), name="create_scale"),
    path('delete_exam_scale/<int:scale_pk><int:exam_pk>', views.delete_exam_scale, name="delete_exam_scale"),
    path('set_final_scale/<int:pk>', views.set_final_scale, name="set_final_scale"),
    path('documentation',login_required(views.documentation_view), name="documentation"),
] + static(settings.SCANS_URL, document_root=settings.SCANS_ROOT)
    + static(settings.MARKED_SCANS_URL, document_root=settings.MARKED_SCANS_ROOT)
    + static(settings.AMC_PROJECTS_URL, document_root=settings.AMC_PROJECTS_ROOT)
   + static(settings.DOCUMENTATION_URL, document_root=settings.DOCUMENTATION_ROOT)
   + static(settings.ROOMS_PLANS_URL, document_root=settings.ROOMS_PLANS_ROOT)
)

urlpatterns += django_tequila_urlpatterns
