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
from django.urls import path
from AutoRad.views import home, upload_image, process_image, view_mask, get_control_points



urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    path('upload-path/', upload_image, name='upload_image'),
    path('api/process-image/', process_image, name='process_image'),
    path('api/view-mask/', view_mask, name='view_mask'),
    path('api/get-control-points/', get_control_points, name='get_control_points')
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)