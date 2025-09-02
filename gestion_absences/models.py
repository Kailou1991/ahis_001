from django.db import models
from gestion_resources.models import Employe
from datetime import timedelta

class TypeConge(models.Model):
    TYPE_CONGE_CHOICES = [
        ('maladie', 'Maladie'),
        ('annuel', 'Annuel'),
        ('maternite', 'Maternité'),
        ('paternite', 'Paternité'),
        ('parental', 'Parental'),
        ('sabbatique', 'Sabbatique'),
        ('evenement_familial', 'Événement familial'),
        ('formation', 'Formation'),
    ]

    nom = models.CharField(max_length=20, choices=TYPE_CONGE_CHOICES, default='annuel')
    description = models.TextField()
    nombreJour = models.IntegerField(default=30)  # Ajout d'une valeur par défaut

    def __str__(self):
        return self.nom
    
class Conge(models.Model):
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE)
    type_conge = models.ForeignKey(TypeConge, on_delete=models.CASCADE)
    date_debut = models.DateField()
    date_fin = models.DateField()
    duree = models.IntegerField(editable=False)  # Durée en jours, non modifiable via le formulaire
    solde = models.IntegerField(editable=False,null=True)  # solde en jours, non modifiable via le formulaire
    statut = models.CharField(max_length=20, choices=[('approuvé', 'Approuvé'), ('en_attente', 'En attente'), ('refusé', 'Refusé')])
    remarque = models.TextField()

    def __str__(self):
        return f"Congé de {self.employe} ({self.type_conge})"

    def save(self, *args, **kwargs):
        # Calculer la durée en jours
        if self.date_debut and self.date_fin:
            self.duree = (self.date_fin - self.date_debut).days + 1  # Inclure le jour de début
        super().save(*args, **kwargs)