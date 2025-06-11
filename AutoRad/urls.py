"""AutoRad URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
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
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include, reverse_lazy
from django.contrib.auth.views import LogoutView, LoginView

import AutoRad.views


urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth related paths
    path('accounts/login/', LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('accounts/logout/', LogoutView.as_view(next_page=reverse_lazy('login')), name='logout'),
    path('accounts/signup/', AutoRad.views.SignUpView.as_view(), name='signup'),

    # Include default Django auth URLs for good measure (includes password reset)
    path('accounts/', include('django.contrib.auth.urls')),

    # Application paths
    path('', AutoRad.views.home, name='home'),
    path('saveImg/', AutoRad.views.saveImg, name='saveImg'),
    path('assessment/<int:patient_id>/', AutoRad.views.assessment_view, name='assessment'),
    path('api/get-mri-path/', AutoRad.views.get_mri_path, name='get_mri_path'),
    path('api/process-mri-for-view/', AutoRad.views.process_mri_for_view, name='process_mri_for_view'),
    # path('upload-path/', upload_image, name='upload_image'), //This is not in use
    path('api/process-image/', AutoRad.views.process_image, name='process_image'),
    path('api/view-mask/', AutoRad.views.view_mask, name='view_mask'),
    path('api/get-control-points/', AutoRad.views.get_control_points, name='get_control_points'),
    path('api/upload-mask/', AutoRad.views.upload_mask, name='upload_mask'),
    path('api/save-image/', AutoRad.views.save_image, name='save_image'),
    path('delete/<str:mri_id>', AutoRad.views.delete, name='delete'),
    path('api/generate-tag/', AutoRad.views.generate_tag, name='generate_tag'),
    path('api/compile-report/', AutoRad.views.compile_report, name='compile_report')
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)