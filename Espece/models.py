from django.db import models

# Create your models here.
from django.db import models

class Espece(models.Model):
    BOVINS = 'Bovins'
    OVINS= 'Ovins'
    CAPRINS='Caprins'
    CAMELIDES = 'Camelidés'
    EQUINS = 'Équins'
    ASINS='Asins'
    PORCINS = 'Porcins'
    VOLAILLE = 'Volaille'
    CANINS= 'Canins'
    ESPECES_AQUATIQUES = 'Espèces aquatiques'

    ESPECE_CHOICES = [
        (BOVINS, 'Bovins'),
        (OVINS, 'Ovins'),
        (CAPRINS, 'Caprins'),
        (ASINS, 'Asins'),
        (CAMELIDES, 'Camelidés'),
        (EQUINS, 'Équins'),
        (PORCINS, 'Porcins'),
        (VOLAILLE, 'Volaille'),
        (CANINS, 'Canins'),
        (ESPECES_AQUATIQUES, 'Espèces aquatiques'),
    ]
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    Espece = models.CharField(
        max_length=50,
        choices=ESPECE_CHOICES,
    )

    #taux_de_croix = models.FloatField()  # Champ pour le Taux de Croissance

    def __str__(self):
        return f"{self.Espece}"
