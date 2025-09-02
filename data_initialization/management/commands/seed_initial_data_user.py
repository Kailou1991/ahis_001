# accounts/management/commands/seed_initial_data.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from django.db import transaction

# Groupes issus de ton CSV (figés dans le code)
GROUPS = [
    {"id": 1, "name": "Administrateur Système"},
    {"id": 2, "name": "Administrateur Régional"},
    {"id": 3, "name": "Administrateur Départemental"},
    {"id": 4, "name": "Animateur de la Surveillance"},
    {"id": 5, "name": "Superviseur de Campagne"},
    {"id": 6, "name": "Agent de suivi de demande"},
    {"id": 7, "name": "Gestionnaire des Médicaments"},
    {"id": 8, "name": "Directeur de la Santé Animale"},
    {"id": 9, "name": "RH admin"},
    {"id": 10, "name": "Directeur Générale des services vétérinaires"},
    {"id": 11, "name": "Santé publique"},
    {"id": 12, "name": "Services vétérinaires à l'aéroport"},
    {"id": 13, "name": "Services vétérinaires au port"},
    {"id": 14, "name": "Réceptioniste"},
    {"id": 15, "name": "Directeur de laboratoire"},
    {"id": 16, "name": "Analyste"},
]

SUPERUSER = {
    "username": "ahisadmin",
    "password": "ahis123456",
    "email": "ahis@example.com",
    "first_name": "AHIS",
    "last_name": "SuperUser",
    "admin_group_name": "Administrateur Système",
}


class Command(BaseCommand):
    help = "Seed initial data: groupes (figés) + superutilisateur 'ahis' lié au groupe Administrateur Système"

    @transaction.atomic
    def handle(self, *args, **options):
        # 1) Créer/assurer l'existence des groupes par NOM
        self.stdout.write(self.style.SUCCESS("==> Création/validation des groupes"))
        for g in GROUPS:
            name = (g.get("name") or "").strip()
            if not name:
                continue
            group, created = Group.objects.get_or_create(name=name)
            if created:
                self.stdout.write(self.style.SUCCESS(f"  + Groupe créé : {name}"))
            else:
                self.stdout.write(f"  = Groupe déjà existant : {name}")

        # 2) Créer le superutilisateur si absent
        self.stdout.write(self.style.SUCCESS("\n==> Création/validation du superutilisateur"))
        if not User.objects.filter(username=SUPERUSER["username"]).exists():
            user = User.objects.create_superuser(
                username=SUPERUSER["username"],
                email=SUPERUSER["email"],
                password=SUPERUSER["password"],
            )
            user.first_name = SUPERUSER["first_name"]
            user.last_name = SUPERUSER["last_name"]
            user.save()
            self.stdout.write(self.style.SUCCESS(f"  + Superutilisateur '{SUPERUSER['username']}' créé"))
        else:
            user = User.objects.get(username=SUPERUSER["username"])
            self.stdout.write(f"  = Superutilisateur '{SUPERUSER['username']}' déjà existant")

        # 3) Lier le superutilisateur UNIQUEMENT au groupe Administrateur Système
        self.stdout.write(self.style.SUCCESS("\n==> Liaison du superutilisateur à son groupe"))
        try:
            admin_group = Group.objects.get(name=SUPERUSER["admin_group_name"])
            # On s'assure qu'il n'est pas dans d'autres groupes si tu veux être strict :
            # user.groups.clear()
            user.groups.add(admin_group)
            self.stdout.write(self.style.SUCCESS(
                f"  + Ajouté au groupe '{SUPERUSER['admin_group_name']}'"
            ))
        except Group.DoesNotExist:
            self.stdout.write(self.style.ERROR(
                f"  ! Groupe '{SUPERUSER['admin_group_name']}' introuvable (vérifier la liste GROUPS)"
            ))

        self.stdout.write(self.style.SUCCESS("\nSeed terminé ✅"))
