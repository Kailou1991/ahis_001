from django.db import models
from django.contrib.auth.models import User
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune

class TypeInfrastructure(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.nom

class TypeFinancement(models.Model):
    nom = models.CharField(max_length=100, unique=True)
    def __str__(self):
        return self.nom

class EtatInfrastructure(models.Model):
    libelle = models.CharField(max_length=50)
    def __str__(self):
        return self.libelle
        
TYPE_PROPRIETAIRE_CHOICES = [
    ('PUBLIQUE', 'Publique'),
    ('PRIVEE', 'Privée')
]

SEXE_CHOICES = [
    ('HOMME', 'Homme'),
    ('FEMME', 'Femme')
]

class Infrastructure(models.Model):
    # Informations générales
    nom = models.CharField(max_length=255)
    type_infrastructure = models.ForeignKey(TypeInfrastructure, on_delete=models.CASCADE)
    type_proprietaire = models.CharField(max_length=10, choices=TYPE_PROPRIETAIRE_CHOICES, default='PUBLIQUE')
    type_financement = models.ForeignKey(TypeFinancement, on_delete=models.SET_NULL, null=True, blank=True)
    etat_initial = models.ForeignKey(EtatInfrastructure, on_delete=models.SET_NULL, null=True, related_name='etat_initial')
    date_construction = models.DateField(null=True, blank=True)
    commentaire = models.TextField(blank=True, null=True)

    # Localisation
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE)
    localite = models.CharField(max_length=100)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # Propriétaire
    nom_proprietaire = models.CharField(max_length=255, blank=True, null=True)
    grade_proprietaire = models.CharField(max_length=100, blank=True, null=True)
    adresse_proprietaire = models.CharField(max_length=255, blank=True, null=True)
    telephone_proprietaire = models.CharField(max_length=20, blank=True, null=True)
    email_proprietaire = models.EmailField(blank=True, null=True)
    piece_identite_proprietaire = models.CharField(max_length=100, blank=True, null=True)
    numero_piece_identite = models.CharField(max_length=100, blank=True, null=True)
    date_naissance_proprietaire = models.DateField(blank=True, null=True)
    sexe_proprietaire = models.CharField(max_length=10, choices=SEXE_CHOICES, blank=True, null=True)

    # Autorisation
    autorisation_ouverture = models.BooleanField(default=False)
    document_autorisation = models.FileField(upload_to='docs/autorisations/', blank=True, null=True)

    # Documents
    photo = models.ImageField(upload_to='infrastructures_photos/', blank=True, null=True)
    
    # Suivi
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    date_mise_a_jour = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.nom} - {self.type_infrastructure.nom}"

class Inspection(models.Model):
    infrastructure = models.ForeignKey(Infrastructure, on_delete=models.CASCADE, related_name='inspections')
    date_inspection = models.DateField()
    etat_derniere_inspection = models.ForeignKey(EtatInfrastructure, on_delete=models.SET_NULL, null=True, related_name='etat_precedent_inspection')
    etat_inspection = models.ForeignKey(EtatInfrastructure, on_delete=models.SET_NULL, null=True, related_name='etat_courant_inspection')
    inspecteur = models.CharField(max_length=100)
    commentaire = models.TextField(blank=True)

    def __str__(self):
        return f"{self.infrastructure.nom} - {self.date_inspection}"

class HistoriqueEtatInfrastructure(models.Model):
    inspection = models.ForeignKey(Inspection, on_delete=models.CASCADE, related_name='historique_etats')
    infrastructure = models.ForeignKey(Infrastructure, on_delete=models.CASCADE)
    date_modification = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    etat_inspection = models.ForeignKey(EtatInfrastructure, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"{self.infrastructure.nom} - {self.etat_inspection} ({self.date_modification.date()})"
