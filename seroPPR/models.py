from django.db import models

TYPE_ENQUETE_CHOICES = [
    ('T0', 'T0'),
    ('T1', 'T1'),
    ('T2', 'T2'),
]

class resultatAnimal(models.Model):
    maladie = models.CharField(max_length=255)
    region = models.CharField(max_length=255)
    commune = models.CharField(max_length=255)
    village = models.CharField(max_length=255)
    numero_animal_preleve = models.CharField(max_length=255)
    espece_prelevee = models.CharField(max_length=255)
    race = models.CharField(max_length=255)
    sexe = models.CharField(max_length=10)  # Ex : "Mâle", "Femelle"
    classe_age = models.CharField(max_length=100)  # Ex : "Jeune", "Adulte"
    vaccine = models.BooleanField(default=False)
    marque = models.BooleanField(default=False)
    resultat_labo = models.CharField(max_length=255, null=True, blank=True)
    densite_optique = models.FloatField(null=True, blank=True)
    statut = models.CharField(max_length=255)
    type_enquete = models.CharField(max_length=100, choices=TYPE_ENQUETE_CHOICES, default='T0')

    def __str__(self):
        return f"Prélèvement {self.numero_animal_preleve} - {self.espece_prelevee}"


# Résultat Village
class ResultatVillage(models.Model):
    type_enquete = models.CharField(max_length=100, choices=TYPE_ENQUETE_CHOICES)
    region = models.CharField(max_length=255)
    commune = models.CharField(max_length=255)
    village = models.CharField(max_length=255)
    positif = models.IntegerField()
    negatif = models.IntegerField()
    douteux = models.IntegerField()
    effectif_preleve_valable = models.IntegerField()
    prob = models.FloatField()

    


# Résultat Commune
class ResultatCommune(models.Model):
    type_enquete = models.CharField(max_length=100, choices=TYPE_ENQUETE_CHOICES)
    region = models.CharField(max_length=255)
    commune = models.CharField(max_length=255)
    somme_prob_village = models.FloatField()
    nb_total_village_com = models.IntegerField()
    nb_village_echan_com = models.IntegerField()
    prob_commune = models.FloatField()


# Résultat Région
class ResultatRegion(models.Model):
    type_enquete = models.CharField(max_length=100, choices=TYPE_ENQUETE_CHOICES)
    region = models.CharField(max_length=255)
    nb_com_ech = models.IntegerField()
    nb_com_region = models.IntegerField()
    somme_prob_commune_par_region = models.FloatField()
    proportion_poids_region_pays = models.FloatField()
    ponderation_prevalence_relative = models.FloatField()
    variance_relative = models.FloatField()
    prevalence_estimee = models.FloatField()


# Résultat National
class ResultatNational(models.Model):
    type_enquete = models.CharField(max_length=100, choices=TYPE_ENQUETE_CHOICES)
    taux_prevalence_nationale = models.FloatField()
    erreur_standard = models.FloatField()
    intervalle_confiance_inferieur = models.FloatField()
    intervalle_confiance_superieur = models.FloatField()
