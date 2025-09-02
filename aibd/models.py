from django.db import models

class Continent(models.Model):
    code = models.CharField(max_length=2, unique=True)
    nom = models.CharField(max_length=50)

    def __str__(self):
        return self.nom

class PaysMonde(models.Model):
    code = models.CharField(max_length=10, unique=True)
    nom = models.CharField(max_length=100)
    continent = models.ForeignKey(Continent, on_delete=models.SET_NULL, null=True, related_name="pays")

    def __str__(self):
        return self.nom

class ServiceVeterinaireAIBD(models.Model):
    TYPE_OPERATION_CHOICES = [
        ('importation', 'Importation'),
        ('exportation', 'Exportation')
    ]

    TYPE_CHOICES = [
        ('Animaux', 'Animaux'),
        ('POD', 'POD'),
        ('Medicaments', 'Médicaments')
    ]

    date = models.DateField(verbose_name="Date")
    type_operation = models.CharField(max_length=20, choices=TYPE_OPERATION_CHOICES, verbose_name="Type d'opération")
    expediteur = models.CharField(max_length=255, verbose_name="Expéditeur/Importateur")
    lta = models.CharField(max_length=100, null=True, blank=True, verbose_name="LTA")
    continent = models.ForeignKey(Continent, on_delete=models.SET_NULL, null=True, verbose_name="Continent")
    pays = models.ForeignKey(PaysMonde, on_delete=models.SET_NULL, null=True, verbose_name="Pays")
    type_produit = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name="Type de produit")
    produit = models.CharField(max_length=100, verbose_name="Produit")
    quantite = models.FloatField(verbose_name="Quantité / Nombre")
    numero_vol = models.CharField(max_length=100, null=True, blank=True, verbose_name="Numéro de vol")
    date_vol = models.DateField(null=True, blank=True, verbose_name="Date de vol")
    societe_transit = models.CharField(max_length=255, null=True, blank=True, verbose_name="Société de transit")
    observations = models.TextField(null=True, blank=True, verbose_name="Observations")
    Idkobo = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID kobo")
  
    def __str__(self):
        return f"{self.date} - {self.type_operation} - {self.pays}"
