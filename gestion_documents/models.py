from django.db import models
from gestion_resources.models import Employe
# Modèle pour la gestion des documents administratifs des employés
class Document(models.Model):
    TYPE_DOCUMENT_CHOICES = [
        ('contrat_travail', 'Contrat de travail'),
        ('certificat_travail', 'Certificat de travail'),
        ('certificat_competence', 'Certificat de compétence'),
        ('certificat_medical', 'Certificat médical'),
        ('rapport_evaluation', 'Rapport d\'évaluation de performance'),
        ('rapport_formation', 'Rapport de formation'),
        ('fiche_paie', 'Fiche de paie'),
        ('demande_conge', 'Demande de congé'),
        ('approbation_conge', 'Approbation de congé'),
        ('releve_conge', 'Relevé de congé'),
        ('carte_identite', 'Carte d\'identité'),
        ('passeport', 'Passeport'),
        ('permis_conduire', 'Permis de conduire'),
        ('attestation_formation', 'Attestation de formation'),
        ('certificat_participation', 'Certificat de participation'),
        ('attestation_affiliation', 'Attestation d\'affiliation'),
        ('declaration_cotisations', 'Déclaration de cotisations'),
        ('declaration_impots', 'Déclaration d\'impôts'),
        ('certificat_retenue_source', 'Certificat de retenue à la source'),
        ('avertissement', 'Avertissement'),
        ('sanction_disciplinaire', 'Sanction disciplinaire'),
        ('note_service', 'Note de service'),
        ('correspondance_officielle', 'Correspondance officielle'),
        ('autorisation_diverse', 'Autorisation diverse'),
        ('autre', 'Autre'),
    ]

    employe = models.ForeignKey(Employe, on_delete=models.CASCADE)
    nom = models.CharField(max_length=255,null=True)
    type_document = models.CharField(max_length=255, choices=TYPE_DOCUMENT_CHOICES,null=True)
    date_ajout = models.DateField(auto_now_add=True)
    fichier = models.FileField(upload_to='documents_employes/')

    class Meta:
        verbose_name = "Document Administratif"
        verbose_name_plural = "Documents Administratifs"

    def __str__(self):
        return f"Document {self.nom} - {self.employe.nom}"
    