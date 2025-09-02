from django.db import models

class Structure(models.Model):
    id = models.AutoField(primary_key=True)
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
     
    structure = models.CharField(max_length=255)  # Nom de la structure

    def __str__(self):
        return self.structure
