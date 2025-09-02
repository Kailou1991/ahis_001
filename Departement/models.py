from django.db import models

# Create your models here.
from django.db import models
from Region.models import Region

# Create your models here.
class Departement(models.Model):
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    Nom = models.CharField(max_length=100,null=False,blank=False)
    Region=models.ForeignKey(Region,null=True,blank=True,on_delete=models.CASCADE)


    def __str__(self):
        return self.Nom


