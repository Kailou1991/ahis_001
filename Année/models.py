from django.db import models

# Create your models here.
from django.db import models
from datetime import datetime
from django.contrib.auth.models import User



def get_year_choices():
    current_year = datetime.now().year
    return [(year, str(year)) for year in range(2020, current_year + 1)]

# Create your models here.


class Année(models.Model):
    annee = models.IntegerField(choices=get_year_choices())
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    def __str__(self):
        return str(self.annee)

