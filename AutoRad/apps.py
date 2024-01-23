from django.apps import AppConfig
from .model import load_model
class AutoRadConfig(AppConfig):
    name = 'AutoRad'

    def ready(self):
        load_model()