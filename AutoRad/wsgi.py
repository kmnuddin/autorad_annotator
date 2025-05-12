"""
WSGI config for AutoRad project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.1/howto/deployment/wsgi/
"""

import os
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AutoRad.settings')
application = get_wsgi_application()

# first serve your STATIC_ROOT (already done)
application = WhiteNoise(application, root=settings.STATIC_ROOT)

# then also serve your MEDIA_ROOT under /media/
application.add_files(settings.MEDIA_ROOT, prefix=settings.MEDIA_URL)

