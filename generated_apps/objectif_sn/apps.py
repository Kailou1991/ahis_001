from django.apps import AppConfig

class ObjectifSnConfig(AppConfig):
    name = "generated_apps.objectif_sn"
    verbose_name = "Intégration Kobo – Objectifs"

    def ready(self):
        from . import signals  # noqa: F401
