from django.apps import AppConfig


class DataInitializationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "data_initialization"

    def ready(self):
        # Importer et enregistrer les signaux
        import data_initialization.signals
