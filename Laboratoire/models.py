from django.db import models
from Pays.models import Pays
# Create your models here.

class Laboratoire(models.Model):
    id = models.AutoField(primary_key=True)  # ID auto-incrémenté
    laboratoire = models.CharField(max_length=100) 
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return self.laboratoire