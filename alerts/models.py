# alerts/models.py
from django.db import models

class DestinataireAlerte(models.Model):
    TYPE_CHOICES = [
        ('Vaccination', 'Vaccination'),
        ('Rapportage', 'Rapportage'),
    ]

    nom = models.CharField(max_length=100, blank=True, null=True, help_text="Nom du destinataire")
    email = models.EmailField(unique=True)
    formulaire=models.CharField("formulaire",max_length=100, blank=True, null=True, help_text="Nom du formulaire",choices=TYPE_CHOICES, default='Vaccination')
    actif = models.BooleanField(default=True, help_text="Cocher pour recevoir les alertes")

    def __str__(self):
        return f"{self.nom or self.email} ({'actif' if self.actif else 'inactif'})"
