from django.db import models

class TypeTestLabo(models.Model):
    id = models.AutoField(primary_key=True)  # ID auto-incrémenté
    test = models.CharField(max_length=255)  # Type de test de laboratoire

    def __str__(self):
        return self.test
