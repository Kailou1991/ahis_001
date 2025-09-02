from django.db import models


class Ministere(models.Model):
    nom = models.CharField(
        max_length=255,
        help_text="Nom complet du ministère"
    )
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Ministère"
        verbose_name_plural = "Ministères"

    def __str__(self):
        return self.nom


class DirectionSV(models.Model):
    nom = models.CharField(
        max_length=255,
        help_text="Nom complet de la Direction des Services Vétérinaires"
    )
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Direction des Services Vétérinaires"
        verbose_name_plural = "Directions des Services Vétérinaires"

    def __str__(self):
        return self.nom