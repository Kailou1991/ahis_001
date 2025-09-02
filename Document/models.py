from django.db import models

class Document(models.Model):
    TYPE_DOCUMENT_CHOICES = [
        ('LOI', 'Loi'),
        ('REGLEMENTATION_NATIONALE', 'Réglementation nationale'),
        ('REGLEMENTATION_INTERNATIONALE', 'Réglementation internationale'),
        ('ARRETE_MINISTERIEL', 'Arrêté ministériel'),
         ('DECRET', 'Decret'),
        ('DIRECTIVE', 'Directive'),
        ('GUIDELINE', 'Ligne directrice'),
        ('CIRCULAIRE', 'Circulaire'),
        ('PROCEDURE', 'Procédure'),
        ('MEMO', 'Mémo'),
        ('NORME', 'Norme'),
        ('NOTE', 'Note'),
        ('LETTRE', 'Lettre'),
        ('REGLEMENTATION_REGIONALE', 'Réglementation régionale'),
        ('POLITIQUE', 'Politique'),
        ('ETUDE', 'Étude'),
    ]
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
    id = models.AutoField(primary_key=True)
    type_document = models.CharField(max_length=50, choices=TYPE_DOCUMENT_CHOICES)
    libelle = models.CharField(max_length=255)
    date_de_mise_en_application = models.DateField()
    date_de_publication = models.DateField(null=True, blank=True)  # Date de publication
    autorite_emission = models.CharField(max_length=255)
    version = models.CharField(max_length=50, blank=True, null=True)  # Version du document
    fichier = models.FileField(upload_to='documents/', blank=True, null=True)
    mots_cles = models.CharField(max_length=255, blank=True, null=True)  # Mots clés pour la recherche
    description = models.TextField(blank=True, null=True)  # Description détaillée du document
    valide = models.BooleanField(default=True)  # Indicateur de validité du document

    class Meta:
        ordering = ['date_de_mise_en_application']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

    def __str__(self):
        return f"{self.libelle} ({self.type_document})"

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('document_detail', args=[str(self.id)])
