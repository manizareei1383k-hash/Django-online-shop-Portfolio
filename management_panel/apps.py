from django.apps import AppConfig


class ManagementPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'management_panel'

    def ready(self):
        from . import signals  # noqa: F401
