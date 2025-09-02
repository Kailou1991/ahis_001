from django.db import models
from Region.models import Region
from Espece.models import Espece
from Année.models import Année
from Departement.models import Departement
from Commune.models import Commune
# Create your models here.
class Effectif(models.Model):
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    id = models.AutoField(primary_key=True)  # Auto-incremented ID
    Espece = models.ForeignKey(Espece, on_delete=models.CASCADE)
    Effectif = models.IntegerField()
    Annee = models.ForeignKey(Année, on_delete=models.CASCADE)  # Clé étrangère vers Annee
    Region = models.ForeignKey(Region, on_delete=models.CASCADE)
    Departement = models.ForeignKey(Departement, on_delete=models.CASCADE)
    Commune = models.ForeignKey(Commune, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.Espece} - {self.Effectif} - {self.Region} - {self.Departement} - {self.Commune}({self.Annee})"

