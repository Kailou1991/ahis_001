from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Inspection, HistoriqueEtatInfrastructure

@receiver(post_save, sender=Inspection)
def enregistrer_historique_etat(sender, instance, created, **kwargs):
    if created:
        HistoriqueEtatInfrastructure.objects.create(
            inspection=instance,
            infrastructure=instance.infrastructure,
            etat_inspection=instance.etat_inspection,
            user=instance.infrastructure.user
        )
