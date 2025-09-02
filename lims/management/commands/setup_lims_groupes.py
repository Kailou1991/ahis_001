from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from lims.models import Demande, Echantillon, Analyse, Rapport, TestCatalogue, LotReactif, Equipement

GROUPES = {
    "LIMS_MANAGER": ["add", "change", "delete", "view"],
    "LAB_CHIEF": ["change", "view"],
    "LIMS_ANALYST": ["add", "change", "view"],
    "LIMS_RECEPTION": ["add", "change", "view"],
    "LIMS_LECTURE": ["view"],
}
MODELES = [Demande, Echantillon, Analyse, Rapport, TestCatalogue, LotReactif, Equipement]

class Command(BaseCommand):
    help = "Crée les groupes et permissions LIMS"

    def handle(self, *args, **kwargs):
        for gname, verbs in GROUPES.items():
            group, _ = Group.objects.get_or_create(name=gname)
            for model in MODELES:
                ct = ContentType.objects.get_for_model(model)
                for v in verbs:
                    codename = f"{v}_{model._meta.model_name}"
                    try:
                        perm = Permission.objects.get(content_type=ct, codename=codename)
                        group.permissions.add(perm)
                    except Permission.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"Permission manquante {codename}"))
            self.stdout.write(self.style.SUCCESS(f"Groupe {gname} OK"))
