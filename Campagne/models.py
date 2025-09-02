from django.db import models
from django.contrib.auth.models import User
from django.db.models.functions import Lower, Trim

class Campagne(models.Model):
    TYPE_CAMPAGNE_CHOICES = [
        ('Masse', 'Masse'),
        ('Ciblee', 'Ciblée'),
    ]

    Campagne = models.CharField("Période de la campagne", max_length=100)  # ex : 2023-2024
    statut = models.BooleanField("Campagne active", default=True)
    type_campagne = models.CharField("Type de campagne", max_length=10, choices=TYPE_CAMPAGNE_CHOICES, default='masse')
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        constraints = [
        models.UniqueConstraint(
            Lower(Trim("Campagne")), "type_campagne",
            name="uniq_campaign_type_ci_trimmed"
        ),
    ]


    def __str__(self):
        return f"{self.Campagne} ({self.get_type_campagne_display()})"




