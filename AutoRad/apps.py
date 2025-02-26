from django.apps import AppConfig
from .utils import load_model
class AutoRadConfig(AppConfig):
    name = 'AutoRad'

    def ready(self):
        import AutoRad.signals
        load_model()