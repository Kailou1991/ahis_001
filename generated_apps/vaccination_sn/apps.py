from django.apps import AppConfig

class VaccinationSnConfig(AppConfig):
    name = "generated_apps.vaccination_sn"
    verbose_name = "Intégration Kobo – Vaccinations"

    def ready(self):
        from . import signals  # noqa: F401
