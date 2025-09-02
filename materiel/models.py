# materiel/models.py
from django.db import models
from django.contrib.auth.models import User

class TypeMateriel(models.Model):
    nom = models.CharField(max_length=150, unique=True, db_index=True)
    class Meta:
        ordering = ["nom"]
        verbose_name = "Type de matériel"
        verbose_name_plural = "Types de matériel"
    def __str__(self):
        return self.nom

class Dotation(models.Model):
    region = models.ForeignKey("Region.Region", on_delete=models.CASCADE, related_name="dotations_materiel")
    campagne = models.ForeignKey("Campagne.Campagne",default=1, on_delete=models.CASCADE, related_name="dotations")  # 🆕 lien
    type_materiel = models.ForeignKey(TypeMateriel, on_delete=models.PROTECT, related_name="dotations")
    quantite = models.PositiveIntegerField(default=0)
    date_dotation = models.DateField("Date de dotation")

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    piece_jointe = models.FileField(upload_to="dotations/pjs/", null=True, blank=True,
                                    verbose_name="Pièce jointe (bon/PV)")
    observations = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # on inclut la campagne dans la contrainte d'unicité
        unique_together = ("type_materiel", "region", "campagne", "date_dotation")
        indexes = [
            models.Index(fields=["region"]),
            models.Index(fields=["type_materiel"]),
            models.Index(fields=["campagne"]),
            models.Index(fields=["date_dotation"]),
        ]
        ordering = ["-date_dotation", "campagne__Campagne", "region__Nom", "type_materiel__nom"]
        verbose_name = "Dotation de matériel"
        verbose_name_plural = "Dotations de matériel"

    def __str__(self):
        d = self.date_dotation.strftime("%d/%m/%Y") if self.date_dotation else "Date non définie"
        return f"{self.type_materiel} – {self.region} – {self.campagne} : {self.quantite} ({d})"



class DotationDoseVaccin(models.Model):
    campagne = models.ForeignKey(
        "Campagne.Campagne",            # adapte la casse du label d'app si besoin (ex: "campagne.Campagne")
        on_delete=models.PROTECT,
        related_name="dotations_doses"
    )
    maladie = models.ForeignKey(
        "Maladie.Maladie",              # adapte selon ton app (ex: "maladie.Maladie")
        on_delete=models.PROTECT,
        related_name="dotations_doses"
    )

    quantite_doses = models.PositiveIntegerField("Quantité (doses)", default=0)
    date_dotation = models.DateField("Date de dotation")

    # Traçabilité (facultatif mais conseillé)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    piece_jointe = models.FileField(
        upload_to="dotations_doses/pjs/", null=True, blank=True,
        verbose_name="Pièce jointe (bon/PV)"
    )
    observations = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # empêche les doublons pour une même campagne/maladie/jour
        unique_together = ("campagne", "maladie", "date_dotation")
        indexes = [
            models.Index(fields=["campagne"]),
            models.Index(fields=["maladie"]),
            models.Index(fields=["date_dotation"]),
        ]
        ordering = ["-date_dotation", "campagne__Campagne", "maladie__Maladie"]
        verbose_name = "Dotation en doses de vaccin"
        verbose_name_plural = "Dotations en doses de vaccin"
        

    def __str__(self):
        d = self.date_dotation.strftime("%d/%m/%Y") if self.date_dotation else "Date non définie"
        return f"{self.campagne} – {self.maladie} : {self.quantite_doses} doses ({d})"
