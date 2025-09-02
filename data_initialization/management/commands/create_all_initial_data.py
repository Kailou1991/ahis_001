import os
import django
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group

# Configurer l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AHIS001.settings')  # Remplacez 'AHIS001' par le nom réel de votre projet
django.setup()

class Command(BaseCommand):
    help = 'Create initial data for the project including groups and user assignments'

    def handle(self, *args, **kwargs):
        # Création des groupes
        groups = [
            'Administrateur Système',
            'Administrateur Régional',
            'Administrateur Départemental',
            'Directeur de la Santé Animale',
            'Superviseur de Campagne',
            'Animateur de la Surveillance',
            'Utilisateur Public',
            'Gestionnaire des Médicaments',
        ]
        
        for group_name in groups:
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Group "{group_name}" created'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Group "{group_name}" already exists'))
        
        # Assurer la présence de l'utilisateur et son ajout au groupe
        username = 'ahis'
        group_name = 'Administrateur Système'
        try:
            user, user_created = User.objects.get_or_create(username=username)
            if user_created:
                self.stdout.write(self.style.SUCCESS(f'User "{username}" created'))
            else:
                self.stdout.write(self.style.SUCCESS(f'User "{username}" already exists'))

            # Assigner l'utilisateur au groupe "Administrateur Système"
            try:
                group = Group.objects.get(name=group_name)
                if not user.groups.filter(name=group_name).exists():
                    user.groups.add(group)
                    self.stdout.write(self.style.SUCCESS(f'User "{username}" added to group "{group_name}"'))
                else:
                    self.stdout.write(self.style.SUCCESS(f'User "{username}" is already in group "{group_name}"'))
            except Group.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Group "{group_name}" does not exist'))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred: {str(e)}'))
