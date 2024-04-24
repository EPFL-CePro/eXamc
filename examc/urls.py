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
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django_tequila.urls import urlpatterns as django_tequila_urlpatterns

from examc_app import views


urlpatterns = ([
    path('admin/doc/', include('django.contrib.admindocs.urls')),
    path('admin/', admin.site.urls),
    path('', include('examc_app.urls')),
    path('', views.home, name='home'),
    path('login_form/', views.log_in, name='login_form'),
    path('logout', views.logout,name='logout'),
    path('home',views.home, name='home'),
    path('examSelect', login_required(views.ExamSelectView.as_view(), login_url='/'), name="examSelect"),
    path('examInfo/<int:pk>', login_required(views.ExamInfoView.as_view(), login_url='/'), name="examInfo"),
    path('select_exam/<int:pk>', login_required(views.select_exam), name="select_exam"),
    path('getCommonExams/<int:pk>', views.getCommonExams, name="getCommonExams"),
    path('documentation',login_required(views.documentation_view), name="documentation"),
] + static(settings.SCANS_URL, document_root=settings.SCANS_ROOT)
    + static(settings.AMC_PROJECTS_URL, document_root=settings.AMC_PROJECTS_ROOT)
   + static(settings.DOCUMENTATION_URL, document_root=settings.DOCUMENTATION_ROOT)
)

urlpatterns += django_tequila_urlpatterns
