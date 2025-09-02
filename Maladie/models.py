from django.db import models

# Create your models here.
from django.db import models
from Espece.models import Espece


# Create your models here.
class Maladie(models.Model):
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    Maladie = models.CharField(max_length=200)
    TYPEMALADIE=(("Animale", "Animale"), ("Zoonotique", "Zoonotique"))
    Type=models.CharField(choices=TYPEMALADIE, max_length=200, default='Animale')
    Espece=models.ManyToManyField(Espece, related_name='maladies')

    def __str__(self):
        return self.Maladie


