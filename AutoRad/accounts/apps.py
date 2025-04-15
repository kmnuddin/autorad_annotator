from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'AutoRad.accounts'
    label = 'accounts'  # This is the app label Django will use.
    default_auto_field = 'django.db.models.BigAutoField'
