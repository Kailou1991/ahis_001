from django.db import models
class Partenaire(models.Model):
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    id = models.AutoField(primary_key=True)  # ID auto-incrémenté
    nom = models.CharField(max_length=100, unique=True)  # Nom du pays

    def __str__(self):
        return self.nom
