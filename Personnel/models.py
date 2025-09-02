from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from Region.models import Region
from Departement.models import Departement
from Structure.models import Structure
from Commune.models import Commune

class Titre(models.Model):
    nom = models.CharField(max_length=50, unique=True)  # Nom du titre (ex: Vétérinaire, Technicien)

    def __str__(self):
        return self.nom
   
class Entite(models.Model):
    nom = models.CharField(max_length=255, unique=True)  # Nom de l'entité (ex: Employé, Vacataire)

    def __str__(self):
        return self.nom

class Personnel(models.Model):
    TYPE_CHOICES = [
        ('ACTIVE', 'Active'),
        ('DETACHE', 'Détaché'),
        ('STAGE', 'Position de stage'),
        ('DISPONIBILITE', 'Disponibilité'),
        ('DECDE', 'Décédé'),
        ('RETRAITE', 'Retraité'),
    ]

    id = models.AutoField(primary_key=True)  # ID auto-incrémenté
    position = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        default='ACTIVE'  # Correction du défaut incohérent
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    entite_administrative = models.ForeignKey(Entite, on_delete=models.CASCADE)  # Clé étrangère vers Entite
    nbre = models.IntegerField(validators=[MinValueValidator(0)])  # Nombre de personnes en fonction (éviter valeurs négatives)
    titre = models.ForeignKey(Titre, on_delete=models.CASCADE)  # Clé étrangère vers Titre
    region = models.ForeignKey(Region, on_delete=models.CASCADE)  # Clé étrangère vers Region
    departement = models.ForeignKey(Departement, null=True, blank=True, on_delete=models.CASCADE)  # Clé étrangère vers Departement
    commune = models.ForeignKey(Commune, null=True, blank=True, on_delete=models.CASCADE)  # Clé étrangère vers Commune
    annee = models.IntegerField()
    created_date = models.DateTimeField(auto_now_add=True)  # Date de création
    updated_date = models.DateTimeField(auto_now=True)  # Date de la dernière mise à jour

    def __str__(self):
        return f"{self.titre} ({self.position}) - {self.entite_administrative} - {self.annee}"

    class Meta:
        indexes = [
            models.Index(fields=['annee']),
            models.Index(fields=['region']),
            models.Index(fields=['position']),
        ]
