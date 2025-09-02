from django.db import models
from jsonschema import ValidationError
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune

# Modèle pour les Directions Générales et Techniques
class Direction(models.Model):
    TYPE_CHOICES = [
        ('GEN', 'Générale'),
        ('TEC', 'Technique'),
    ]
    nom = models.CharField(max_length=255)
    type = models.CharField(max_length=3, choices=TYPE_CHOICES, default='GEN')
    sous_directions = models.ManyToManyField('SousDirection', blank=True, related_name='directions')

    def __str__(self):
        return self.nom

# Modèle pour les Sous-Directions
class SousDirection(models.Model):
    nom = models.CharField(max_length=255)
    direction = models.ForeignKey(Direction, on_delete=models.CASCADE, related_name='sous_directions_set')

    def __str__(self):
        return self.nom

# Modèle pour la gestion des postes
class Poste(models.Model):
    nom = models.CharField(max_length=255)
    description = models.TextField()
    commune = models.ForeignKey(Commune, on_delete=models.SET_NULL, null=True, blank=True)
    departement = models.ForeignKey(Departement, on_delete=models.SET_NULL, null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    date_creation = models.DateField(auto_now_add=True)
    statut = models.CharField(max_length=50, choices=[('occupé', 'Occupé'), ('vacant', 'Vacant')])
    direction = models.ForeignKey(Direction, on_delete=models.SET_NULL, null=True, blank=True)
    sous_direction = models.ForeignKey(SousDirection, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.nom} - {self.commune} - {self.departement} - {self.region}"

# Modèle pour la gestion des grades des employés
class Grade(models.Model):
    nom = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.nom

# Modèle pour la gestion des échelons des employés
class Echelon(models.Model):
    nom = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.nom

# Modèle pour la gestion des informations personnelles et professionnelles des employés
class Employe(models.Model):
    TYPE_CHOICES = [
        ('ACTIVE', 'Active'),
        ('DETACHE', 'Détaché'),
        ('STAGE', 'Position de stage'),
        ('DISPONIBILITE', 'Disponibilité'),
        ('DECDE', 'Décédé'),
        ('RETRAITE', 'Retraité'),
    ]
    CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    matricule = models.CharField(max_length=255, unique=True)
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255)
    date_naissance = models.DateField()
    sexe = models.CharField(max_length=50, choices=CHOICES, default='M')
    adresse = models.TextField()
    telephone = models.CharField(max_length=15)
    email = models.EmailField()
    date_embauche = models.DateField()
    poste = models.ForeignKey(Poste, on_delete=models.SET_NULL, null=True, blank=True)
    position = models.CharField(max_length=50, choices=TYPE_CHOICES, default='ACTIVE')
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True)
    echelon = models.ForeignKey(Echelon, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.nom} {self.prenom}"

 
# Modèle pour l'historique de carrière d'un employé
class HistoriqueCarriere(models.Model):
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE)
    poste = models.ForeignKey(Poste, on_delete=models.SET_NULL, null=True, blank=True)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    type_changement = models.CharField(max_length=255)
    remarque = models.TextField()

    def __str__(self):
        return f"Carrière de {self.employe} - {self.type_changement}"

    def clean(self):
        # Validations pour que la date_fin soit après date_debut
        if self.date_fin and self.date_fin < self.date_debut:
            raise ValidationError('La date de fin doit être après la date de début.')

# Modèle pour suivre les formations des employés
class Formation(models.Model):
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE)
    intitule = models.CharField(max_length=255)
    institution = models.CharField(max_length=255)
    date_debut = models.DateField()
    date_fin = models.DateField()
    diplome_obtenu = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.intitule} - {self.employe.nom}"

# Modèle pour la Direction Générale
class DirectionGenerale(models.Model):
    nom = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.nom

# Modèle pour la Direction Technique
class DirectionTechnique(models.Model):
    nom = models.CharField(max_length=255)
    description = models.TextField()

    def __str__(self):
        return self.nom