from django.db import models
from Departement.models import Departement

# Create your models here.
class Commune(models.Model):
    Nom = models.CharField(max_length=100,null=False,blank=False)
    DepartementID=models.ForeignKey(Departement,on_delete=models.CASCADE,null=True,blank=True)
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return self.Nom


