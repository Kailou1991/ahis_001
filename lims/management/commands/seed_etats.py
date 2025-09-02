# lims/management/commands/seed_etats.py
from django.core.management.base import BaseCommand
from lims.models import DemandeEtat   # ✅ correct

ETATS = [
    ("soumise",           "Soumise",                    10, "bi-inbox",                False),
    ("recue",             "Reçue",                      20, "bi-box-arrow-in-down",   False),
    ("affectee",          "Affectée à un analyste",     25, "bi-person-check",        False),
    ("reaffectee",        "Réaffectée",                 28, "bi-arrow-repeat",        False),  # 🆕
    ("analyse_demarre",   "Analyse démarrée",           30, "bi-play-fill",           False),
    ("analyse_terminee",  "Analyse terminée",           35, "bi-flag-checkered",      False),
    ("resultat_transmis", "Résultat brut transmis",     37, "bi-send",                False),
    ("resultat_saisi",    "Résultat brut saisi",        38, "bi-pen",                 False),
    ("valide_tech",       "Validée technique",          40, "bi-check-circle",        False),
    ("valide_bio",        "Validée biologique",         50, "bi-patch-check",         False),
    ("rapportee",         "Rapportée",                  60, "bi-file-earmark-text",   True),
    ("annulee",           "Annulée",                    99, "bi-x-octagon",           True),
]

class Command(BaseCommand):
    help = "Peuple le référentiel des états de demande"

    def handle(self, *args, **kwargs):
        for code, label, ordre, icon, is_terminal in ETATS:
            obj, created = DemandeEtat.objects.update_or_create(
                code=code,
                defaults={
                    "label": label,
                    "ordre": ordre,
                    "icon": icon,
                    "is_terminal": is_terminal,
                },
            )
            action = "Créé" if created else "Mis à jour"
            self.stdout.write(f"{action} : {obj.label} ({obj.code})")

        self.stdout.write(self.style.SUCCESS("✔ États de demande initialisés."))
