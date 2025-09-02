from django.db import models
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune
from Espece.models import Espece
from django.contrib.auth.models import User
from multiselectfield import MultiSelectField


class RegistreAbattage(models.Model):
    AGE_CHOICES = [('jeune', 'Jeunes'), ('adulte', 'Adultes')]
    SEXE_CHOICES = [
        ('males_entiens', 'Mâles entiers'),
        ('males_castres', 'Mâles castrés'),
        ('femelles', 'Femelles')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE)
    espece = models.ForeignKey(Espece, on_delete=models.CASCADE)

    ages = models.CharField(max_length=50, choices=AGE_CHOICES)
    sexes = models.CharField(max_length=20, choices=SEXE_CHOICES)
    nombres = models.IntegerField()
    poids = models.IntegerField(help_text="en kg")
    valeur_financiere = models.IntegerField(help_text="en FCFA")
    observations = models.TextField(blank=True, null=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.espece} - {self.commune} - {self.nombres} animaux"


class RegistreInspectionAnteMortem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE)
    espece = models.ForeignKey(Espece, on_delete=models.CASCADE)

    anomalies = models.CharField(max_length=255)
    symptomes = models.CharField(max_length=255)
    nombres = models.IntegerField()
    poids = models.IntegerField(help_text="en kg")
    valeur_financiere = models.IntegerField(help_text="en FCFA")
    observations = models.TextField(blank=True, null=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Inspection {self.espece} - {self.commune}"


class RegistreSaisiesTotales(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE)
    espece = models.ForeignKey(Espece, on_delete=models.CASCADE)

    motifs_saisies =models.CharField(max_length=255)
    nombres = models.IntegerField()
    poids = models.IntegerField(help_text="en kg")
    valeur_financiere = models.IntegerField(help_text="en FCFA")
    observations = models.TextField(blank=True, null=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Saisie Totale - {self.espece} - {self.commune}"


class RegistreSaisiesOrganes(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE)
    espece = models.ForeignKey(Espece, on_delete=models.CASCADE)

    organes_saisis = models.CharField(max_length=255)
    motifs_saisies_organes = models.CharField(max_length=255)
    nombres = models.IntegerField()
    poids = models.IntegerField(help_text="en kg")
    valeur_financiere = models.IntegerField(help_text="en FCFA")
    observations = models.TextField(blank=True, null=True)
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Saisie Organe - {self.espece} - {self.commune}"


class InspectionViande(models.Model):
    abattoir = models.CharField(max_length=255)
    date_inspection = models.DateField()
    inspecteur = models.CharField(max_length=255)
    numero_lot = models.CharField(max_length=100)
    espece = models.ForeignKey(Espece, on_delete=models.CASCADE)
    ETAT_CHOICES = [('bon', 'Bon'), ('suspect', 'Suspect'), ('mauvais', 'Mauvais')]
    etat_animal = models.CharField(max_length=20, choices=ETAT_CHOICES)

    SIGNES_CHOICES = [
        ('fievre', 'Fièvre'),
        ('boiterie', 'Boiterie'),
        ('lesions_cutanees', 'Lésions cutanées'),
        ('signes_neuro', 'Signes neurologiques'),
        ('autres', 'Autres'),
    ]
    signes_anormaux = models.CharField(max_length=255, choices=SIGNES_CHOICES)
    autre_signe_anormal = models.CharField(max_length=255, blank=True, null=True)

    ASPECT_CHOICES = [
        ('normal', 'Normal'),
        ('decoloration', 'Décoloration'),
        ('lesions', 'Lésions visibles'),
        ('parasites', 'Parasites'),
        ('autre', 'Autre'),
    ]
    aspect_carcasse = models.CharField(max_length=50, choices=ASPECT_CHOICES)

    ORGANE_CHOICES = [('normal', 'Normal'), ('anomalie', 'Anomalie')]
    poumons = models.CharField(max_length=10, choices=ORGANE_CHOICES)
    foie = models.CharField(max_length=10, choices=ORGANE_CHOICES)
    rate = models.CharField(max_length=10, choices=ORGANE_CHOICES)
    coeur = models.CharField(max_length=10, choices=ORGANE_CHOICES)

    description_anomalies = models.TextField(blank=True, null=True)
    
    observations = models.TextField(blank=True, null=True)
    signature_inspecteur = models.CharField(max_length=255, blank=True, null=True)

    date_enregistrement = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.abattoir} - {self.espece} - {self.date_inspection}"
