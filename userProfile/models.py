from django.contrib.auth.models import User, Group
from django.db import models
from Region.models import Region
from Departement.models import Departement

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    departement = models.ForeignKey(Departement, on_delete=models.SET_NULL, null=True, blank=True)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.user.username
