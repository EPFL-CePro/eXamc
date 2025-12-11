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
from django.http import HttpResponse
from django.urls import path, include

from examc_app import views
from examc_app.admin import ExamAdmin, CourseAdmin


def healthz(_request):  # simple 200
    return HttpResponse("ok", content_type="text/plain")
urlpatterns = ([
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),
    path('django-summernote/', include('django_summernote.urls')),
    path('', include('examc_app.urls')),
    path('', views.home, name='home'),
    path('login_form/', views.log_in, name='login_form'),
    path('home',views.home, name='home'),
    path('admin/exam/import_exams_data/', ExamAdmin.import_exams_csv_data),
    path('admin/course/import_courses_data/', CourseAdmin.import_courses_json_data),
    path('examSelect', views.ExamSelectView.as_view(), name="examSelect"),
    path('select_exam/<int:pk>', views.select_exam, name="select_exam"),
    path('getCommonExams/<int:pk>', views.getCommonExams, name="getCommonExams"),
    path('documentation',views.documentation_view, name="documentation"),
    path('oidc/', include('mozilla_django_oidc.urls')),
    #Signed files url
    path("protected/", views.serve_signed_file, name="serve_signed_file"),
    path('force-logout/', views.force_oidc_logout, name='force_oidc_logout'),
    path("healthz/", healthz, name="healthz"),
    ] #+ static(settings.MARKED_SCANS_URL, document_root=settings.MARKED_SCANS_ROOT)
    #+ static(settings.AMC_PROJECTS_URL, document_root=settings.AMC_PROJECTS_ROOT)
   + static(settings.DOCUMENTATION_URL, document_root=settings.DOCUMENTATION_ROOT)
   # + static(settings.ROOMS_PLANS_URL, document_root=settings.ROOMS_PLANS_ROOT)
)

# urlpatterns += django_tequila_urlpatterns
