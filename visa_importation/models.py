from django.db import models
from django.contrib.auth.models import User

class FactureImportationVisee(models.Model):
    numero_facture = models.CharField("Numéro de la facture", max_length=100, unique=True)
    Structure= models.CharField("Nom de la structure", max_length=100,default='Inconnue')
    date_visa_dsv = models.DateField("Date du visa DSV", auto_now_add=True)
    fichier_facture = models.FileField("Facture visée (PDF)", upload_to="factures_visees/")

    vise_par_dsv = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="factures_visees_dsv",
        verbose_name="Visa DSV par"
    )

    est_visa_pif = models.BooleanField("Facture visée par le PIF ?", default=False)
    date_visa_pif = models.DateTimeField("Date visa PIF", null=True, blank=True)
    vise_par_pif = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="factures_visees_pif",
        verbose_name="Visa PIF par"
    )

    commentaire = models.TextField("Commentaire PIF", null=True, blank=True)

    class Meta:
        verbose_name = "Facture importation visée"
        verbose_name_plural = "Factures importation visées"
        ordering = ["-date_visa_dsv"]

    def __str__(self):
        return f"Facture {self.numero_facture}"
