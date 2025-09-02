from django.db import models
from django.contrib.auth.models import User
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune




class EmailNotification(models.Model):
    NIVEAU_CHOICES = [
        ("departemental", "Départemental"),
        ("regional", "Régional"),
        ("central", "Central"),
        ("ordre", "Ordre des vétérinaires"),
        ("ministere", "Ministère"),
    ]

    niveau = models.CharField(max_length=50, choices=NIVEAU_CHOICES)
    email = models.EmailField()
    region = models.ForeignKey(Region, null=True, blank=True, on_delete=models.SET_NULL)
    departement = models.ForeignKey(Departement, null=True, blank=True, on_delete=models.SET_NULL)
    actif = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.email} ({self.niveau})"

class CategorieActe(models.Model):
    code = models.CharField(max_length=50, unique=True)
    nom = models.CharField(max_length=255)
    necessite_avis_ordre = models.BooleanField(default=False)

    def __str__(self):
        return self.nom


    
class TypeActe(models.Model):
    VALIDITE_CHOICES = [
                ("1_mois", "1 mois"),
                ("2_mois", "2 mois"),
                ("3_mois", "3 mois"),
                ("6_mois", "6 mois"),
                ("1_an", "1 an"),
                ("2_ans", "2 ans"),
                ("3_ans", "3 ans"),
                ("sans_limite", "Sans limite")
            ]
    code = models.CharField(max_length=100, unique=True)
    nom = models.CharField(max_length=255)
    categorie = models.ForeignKey(CategorieActe, on_delete=models.CASCADE, related_name='actes')
    prix = models.DecimalField(max_digits=10, decimal_places=2)
    validite = models.CharField(max_length=20, choices=VALIDITE_CHOICES, default="sans_limite")

    def __str__(self):
        return self.nom

class DemandeActe(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,null=True)
    nom = models.CharField(max_length=255)
    prenom = models.CharField(max_length=255)
    grade = models.CharField(max_length=100)
    nationalite = models.CharField(max_length=100)
    contact = models.CharField(max_length=20)
    email = models.EmailField()
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True)
    departement = models.ForeignKey(Departement, on_delete=models.SET_NULL, null=True)
    commune = models.ForeignKey(Commune, on_delete=models.SET_NULL, null=True)

    categorie = models.ForeignKey(CategorieActe, on_delete=models.CASCADE)
    acte = models.ForeignKey(TypeActe, on_delete=models.CASCADE)
    statut = models.CharField(max_length=50, choices=[
        ("en_cours", "En cours"),
        ("valide", "Validé"),
        ("rejete", "Rejeté"),
        ("delivre", "Délivré")
    ], default="en_cours")
    document_final = models.FileField(upload_to='documents_actes_signes/', blank=True, null=True)
    date_soumission = models.DateTimeField(auto_now_add=True)

    # Champs spécifiques par catégorie
    nom_etablissement = models.CharField(max_length=255, blank=True, null=True)  # pour les établissements
    nom_produit_importe_ou_exporte = models.CharField(max_length=255, blank=True, null=True)  # pour import/export
    nom_unité_transformation = models.CharField(max_length=255, blank=True, null=True)  # pour transformation

    def __str__(self):
        return f"Demande de {self.acte.nom} - {self.user.username}"

class Justificatif(models.Model):
    demande = models.ForeignKey(DemandeActe, on_delete=models.CASCADE, related_name='justificatifs')
    fichier = models.FileField(upload_to='justificatifs/')
    nom = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.nom} pour la demande {self.demande.id}"

class SuiviDemande(models.Model):
    demande = models.ForeignKey(DemandeActe, on_delete=models.CASCADE, related_name='suivis')
    niveau = models.CharField(max_length=50, choices=[
        ("departemental", "Départemental"),
        ("regional", "Régional"),
        ("central", "Central"),
        ("ordre", "Ordre des vétérinaires"),
        ("ministere", "Ministère")
    ])
    statut = models.CharField(max_length=50, choices=[
        ("en_cours", "En cours"),
        ("valide", "Validé"),
        ("rejete", "Rejeté"),
        ("delivre", "Délivré")
    ])
    motif_rejet = models.TextField(blank=True, null=True)
    date_action = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.niveau} - {self.statut} ({self.demande.id})"

class AffectationSuivi(models.Model):
    demande = models.ForeignKey(DemandeActe, on_delete=models.CASCADE, related_name='affectations')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demandes_affectees')
    emetteur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demandes_attribuees')
    commentaire = models.TextField(blank=True, null=True)
    date_attribution = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ('demande', 'agent')
        verbose_name = "Affectation de suivi"
        verbose_name_plural = "Affectations de suivi"

    def __str__(self):
        return f"{self.demande} affectée à {self.agent.get_full_name()}"
    

class PieceAFournir(models.Model):
        type_acte = models.ForeignKey(TypeActe, on_delete=models.CASCADE, related_name="pieces")
        nom_piece = models.CharField(max_length=255, verbose_name="Nom de la pièce")
        description = models.TextField(blank=True, null=True, verbose_name="Description ou précision")
        obligatoire = models.BooleanField(default=True, verbose_name="Obligatoire ?")

def __str__(self):
        return f"{self.nom_piece} ({'Obligatoire' if self.obligatoire else 'Optionnelle'})"