from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
import os
#from .models import   # Remplacez 'yourapp' par le nom réel de votre application
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'AHIS001.settings')  # Remplacez 'your_project' par le nom de votre projet
import django
django.setup()

class Command(BaseCommand):
    help = 'Update UserProfile for user "ahis" and assign them to the "Administrateur Système" group'

    def handle(self, *args, **kwargs):
        # Assurez-vous que le groupe existe
        group_name = 'Administrateur Système'
        try:
            group, created = Group.objects.get_or_create(name=group_name)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Group "{group_name}" created'))
            else:
                self.stdout.write(self.style.SUCCESS(f'Group "{group_name}" already exists'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred while creating group: {str(e)}'))
            return
        
        # Assurez-vous que l'utilisateur existe
        username = 'ahis'
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with username "{username}" does not exist'))
            return

        # Mettez à jour ou créez le UserProfile
        try:
            profile, created = User.objects.get_or_create(user=user)
            # Mettre à jour les informations du UserProfile si nécessaire
            profile.region_id = None  # Remplacez None par la valeur appropriée
            profile.departement_id = None  # Remplacez None par la valeur appropriée
            profile.save()
            self.stdout.write(self.style.SUCCESS(f'UserProfile for user "{username}" updated'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'An error occurred while updating UserProfile: {str(e)}'))
        
        # Assigner l'utilisateur au groupe
        if not user.groups.filter(name=group_name).exists():
            user.groups.add(group)
            self.stdout.write(self.style.SUCCESS(f'User "{username}" added to group "{group_name}"'))
        else:
            self.stdout.write(self.style.SUCCESS(f'User "{username}" is already in group "{group_name}"'))
