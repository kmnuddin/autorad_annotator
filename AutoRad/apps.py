from django.apps import AppConfig
from .utils import load_model
import sys
class AutoRadConfig(AppConfig):
    name = 'AutoRad'

    def ready(self):
        import AutoRad.signals

        if any(cmd in sys.argv for cmd in ('collectstatic', 'migrate', 'makemigrations', 'test')):
            return
        load_model()

