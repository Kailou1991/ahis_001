# data_initial/management/commands/create_initial_kobo_config.py

from django.core.management.base import BaseCommand
from data_initialization.models import KoboToolboxConfig

class Command(BaseCommand):
    help = 'Initialise les paramètres de connexion pour KoboToolbox'

    def handle(self, *args, **kwargs):
        KoboToolboxConfig.objects.create(
            kobo_url='http://kf.kobotoolbox.org',
            token_form_vaccination='your_vaccination_token_here',
            uid_form_vaccination='your_vaccination_uid_here',
            uid_form_surveillance='your_surveillance_uid_here',
            token_form_surveillance='your_surveillance_token_here'
        )
        self.stdout.write(self.style.SUCCESS('Paramètres de connexion KoboToolbox créés avec succès'))
