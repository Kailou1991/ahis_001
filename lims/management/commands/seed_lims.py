from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from lims.models import SiteLabo, TestCatalogue

class Command(BaseCommand):
    help = "Données de base LIMS"

    def handle(self, *args, **opts):
        SiteLabo.objects.get_or_create(code="LAB1", defaults={"nom": "Laboratoire Central"})
        tests = [
            ("PCR-FVR", "PCR FVR (Fièvre de la Vallée du Rift)", "PCR", "RVFV", "PCR", "Ct"),
            ("ELISA-PPR", "ELISA PPR Anticorps", "Serologie", "PPRV", "ELISA", "S/P>=0.4"),
        ]
        for code_test, nom_test, section, cible, methode, unite in tests:
            TestCatalogue.objects.get_or_create(code_test=code_test, defaults={
                "nom_test": nom_test, "section": section, "cible": cible, "methode": methode, "unite": unite
            })
        User = get_user_model()
        if not User.objects.filter(username="chef").exists():
            User.objects.create_superuser("chef", "chef@example.com", "ahis12345")
        self.stdout.write(self.style.SUCCESS("Base LIMS créée"))
