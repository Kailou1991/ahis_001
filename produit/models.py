
# Create your models here.
from django.db import models
from Partenaire.models import Partenaire
from Pays.models import Pays
from Structure.models import Structure
from django.core.exceptions import ValidationError

class Produit(models.Model):
    TYPE_PRODUIT_CHOICES = [
        ('MEDICAMENT', 'Médicament vétérinaire'),
        ('SEMENCE_ANIMALE', 'Semence animale'),
        ('MATERIEL_VETERINAIRE', 'Matériel à usage vétérinaire'),
    ]
    TYPE_MEDICAMENT_CHOICES = [
        ('ANTIMICROBIEN', 'Antimicrobien'),
        ('ANTI_INFLAMMATOIRE', 'Anti-inflammatoire'),
        ('VACCIN', 'Vaccin'),
        ('ANALGESIQUE', 'Analgésique'),
        ('HORMONE', 'Hormone'),
        ('SUPPLEMENT_NUTRITIONNEL', 'Supplément nutritionnel'),
        ('ANESTHESIQUE', 'Anesthésique'),
        ('SEDATIF', 'Sédatif'),
        ('DIURETIQUE', 'Diurétique'),
        ('CARDIOVASCULAIRE', 'Cardiovasculaire'),
        ('ANTIHISTAMINIQUE', 'Antihistaminique'),
        ('ANTIDIARRHEIQUE', 'Antidiarrhéique'),
        ('LAXATIF', 'Laxatif'),
        ('IMMUNOSUPPRESSEUR', 'Immunosuppresseur'),
        ('ANTINEOPLASIQUE', 'Antinéoplasique'),
        ('TOPIQUE', 'Topique'),
    ]
    STATUS_CHOICES = [
        ('ACTIF', 'Actif'),
        ('NON_ACTIF', 'Non actif'),
    ]
    ANTIBIOTIQUE_CHOICES = [
        ('AMINOSIDE', 'Aminoside'),
        ('FLUOROQUINOLONE', 'Fluoroquinolone'),
        ('MACROLIDE', 'Macrolide'),
        ('QUINOLONE', 'Quinolone (Autres)'),
        ('PENICILLINE', 'Pénicilline'),
        ('POLYPEPTIDE', 'Polypeptide'),
        ('SULFONAMIDE', 'Sulfonamide (Triméthoprime inclus)'),
        ('TETRACYCLINE', 'Tétracycline'),
        ('ASSO_AMINOSIDE_TETRACYCLINE', 'Association Aminoside + Tétracycline'),
        ('ASSO_AMINOSIDE_PENICILLINE', 'Association Aminoside + Pénicilline'),
        ('ASSO_AMINOSIDE_SULFONAMIDE', 'Association Aminoside + Sulfonamide'),
        ('ASSO_FLUOROQUINOLONE_POLYPEPTIDE', 'Association Fluoroquinolone + Polypeptide'),
        ('ASSO_MACROLIDE_NITROIMIDAZOLE', 'Association Macrolide + Nitroimidazole'),
        ('ASSO_POLYPEPTIDE_TETRACYCLINE', 'Association Polypeptide + Tétracycline'),
        ('ASSO_PENICILLINE_POLYPEPTIDE', 'Association Pénicilline + Polypeptide'),
        ('ASSO_SULFONAMIDE_POLYPEPTIDE', 'Association Sulfonamide + Polypeptide'),
        ('ASSO_SULFONAMIDE_NITROFURANE', 'Association Sulfonamide + Nitrofuranes'),
        ('ASSO_TETRACYCLINE_NITROFURANE', 'Association Tétracycline + Nitrofuranes'),
        ('ASSO_TETRACYCLINE_MACROLIDE_POLYPEPTIDE', 'Association Tétracycline + Macrolide + Polypeptide'),
    ]

    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    id = models.AutoField(primary_key=True)
    type_produit = models.CharField(
        max_length=50,
        choices=TYPE_PRODUIT_CHOICES,
        default='MEDICAMENT',
        verbose_name="Type de produit"
    )
    nom_du_produit = models.CharField(max_length=255)
    classe_therapeutique = models.CharField(
        max_length=50,
        choices=TYPE_MEDICAMENT_CHOICES,
        null=True,
        blank=True
    )
    familles_antibiotiques = models.CharField(
        max_length=100,
        choices=ANTIBIOTIQUE_CHOICES,
        null=True,
        blank=True
    )
    forme_pharmaceutique = models.CharField(max_length=255,null=True,blank=True)
    substances_actives = models.CharField(max_length=255,null=True,blank=True)
    numero_autorisation_AMM = models.CharField(max_length=255, null=True, blank=True)
    numero_decision_AMM = models.CharField(max_length=255, null=True, blank=True)
    date_delivrance_AMM = models.DateField(null=True, blank=True)
    status_AMM = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='ACTIF',
        null=True,
        blank=True

    )

    def clean(self):
        if self.type_produit == 'MEDICAMENT':
            if not self.classe_therapeutique:
                raise ValidationError("Le champ 'classe thérapeutique' est requis pour les médicaments.")
            if self.classe_therapeutique == 'ANTIMICROBIEN' and not self.familles_antibiotiques:
                raise ValidationError("Le champ 'familles d'antibiotiques' est requis pour les antimicrobiens.")
        else:
            self.classe_therapeutique = None
            self.familles_antibiotiques = None

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.nom_du_produit

class Enregistrement(models.Model):
    TYPE_CHOICES = [
        ('FABRICATION', 'Fabrication'),
        ('IMPORTATION', 'Importation'),
        ('DOTATION', 'Dotation'),
        ('EXPORTATION', 'Exportation'),
    ]
    from django.contrib.auth.models import User
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
   
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE)
    type_enregistrement = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        default='IMPORTATION'
    )
    
    # Dotation
    quantité_de_la_dotation = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    partenaire_de_dotation = models.ForeignKey('Partenaire.Partenaire', null=True, blank=True, on_delete=models.CASCADE)
    date_dotation = models.DateField(null=True, blank=True)
    adresse_partenaire_dotation = models.CharField(max_length=100, null=True, blank=True)
    
    # Fabrication
    quantité_fabriquée = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    firme_de_fabrication = models.ForeignKey('Structure.Structure',related_name="Fabricant" ,null=True, blank=True, on_delete=models.CASCADE)
    pays_de_fabrication = models.ForeignKey('Pays.Pays', related_name="pays_de_fabrication", null=True, blank=True, on_delete=models.CASCADE)
    date_de_fabrication = models.DateField(null=True, blank=True)
    
    # Importation
    quantité_importée = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    structure_importatrice = models.ForeignKey('Structure.Structure', related_name="importateur", null=True, blank=True, on_delete=models.CASCADE)
    addresse_importateur = models.CharField(max_length=100, null=True, blank=True)
    date_importation = models.DateField(null=True, blank=True)
    pays_importation = models.ForeignKey('Pays.Pays', related_name="pays_importation", null=True, blank=True, on_delete=models.CASCADE)
    
    # Exportation
    quantité_exportée = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    structure_exportatrice = models.ForeignKey('Structure.Structure', related_name="exportateur", null=True, blank=True, on_delete=models.CASCADE)
    addresse_exportateur = models.CharField(max_length=100, null=True, blank=True)
    date_exportation = models.DateField(null=True, blank=True)
    pays_exportation = models.ForeignKey('Pays.Pays', related_name="pays_exportation", null=True, blank=True, on_delete=models.CASCADE)

    valeur_financiere = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    unité_de_la_quantité = models.CharField(max_length=100, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        # Validation for Dotation
        if self.type_enregistrement == 'DOTATION':
            if not self.quantité_de_la_dotation or not self.partenaire_de_dotation or not self.date_dotation or not self.adresse_partenaire_dotation:
                raise ValidationError("Tous les champs relatifs à la dotation doivent être renseignés.")

        # Validation for Fabrication
        elif self.type_enregistrement == 'FABRICATION':
            if not self.quantité_fabriquée or not self.firme_de_fabrication or not self.date_de_fabrication:
                raise ValidationError("Tous les champs relatifs à la fabrication doivent être renseignés.")
           
        # Validation for Importation
        elif self.type_enregistrement == 'IMPORTATION':
            if not self.quantité_importée or not self.structure_importatrice or not self.addresse_importateur or not self.date_importation or not self.pays_importation:
                raise ValidationError("Tous les champs relatifs à l'importation doivent être renseignés.")

        # Validation for Exportation
        elif self.type_enregistrement == 'EXPORTATION':
            if not self.quantité_exportée or not self.structure_exportatrice or not self.addresse_exportateur or not self.date_exportation or not self.pays_exportation:
                raise ValidationError("Tous les champs relatifs à l'exportation doivent être renseignés.")
    
    def save(self, *args, **kwargs):
        self.clean()  # Call the clean method before saving
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.produit.nom_du_produit} - {self.type_enregistrement}"