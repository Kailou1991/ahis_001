from django.db import models
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune

class AgentInspecteur(models.Model):
    nom = models.CharField(max_length=255)
    fonction = models.CharField(max_length=255)
    service = models.CharField(max_length=255)
    telephone = models.CharField(max_length=20)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    deleted_date = models.DateTimeField(null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.nom


class StructureVente(models.Model):
    TYPE_STRUCTURE = [
        ('GROSSISTE', 'Grossiste'),
        ('Detaillant', 'Détaillant')
    ]
    nom = models.CharField(max_length=255)
    type_structure = models.CharField(max_length=50, choices=TYPE_STRUCTURE)
    gps = models.CharField(max_length=100)
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True)
    departement = models.ForeignKey(Departement, on_delete=models.SET_NULL, null=True)
    commune = models.ForeignKey(Commune, on_delete=models.SET_NULL, null=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    deleted_date = models.DateTimeField(null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.nom


class InspectionEtablissement(models.Model):
    date = models.DateField()
    agent = models.ForeignKey(AgentInspecteur, on_delete=models.SET_NULL, null=True)
    structure = models.ForeignKey(StructureVente, on_delete=models.CASCADE)
    observations_generales = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    deleted_date = models.DateTimeField(null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Inspection du {self.date} - {self.structure.nom}"


class ControleDocumentaireDetaillant(models.Model):
    inspection = models.OneToOneField(InspectionEtablissement, on_delete=models.CASCADE)
    autorisation_exercer = models.CharField(max_length=10, choices=[('oui', 'Oui'), ('non', 'Non')])
    nombre_personnel = models.IntegerField(null=True, blank=True)
    qualification = models.TextField(blank=True)
    observations_personnel = models.TextField(blank=True)
    sources_approvisionnement = models.TextField(blank=True)
    registre_ventes_mv = models.CharField(max_length=10, choices=[('oui', 'Oui'), ('non', 'Non')])
    observations_registres = models.TextField(blank=True)
    enseigne = models.CharField(max_length=10, choices=[('oui', 'Oui'), ('non', 'Non')])
    observations_enseigne = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    deleted_date = models.DateTimeField(null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)


class VerificationPhysiqueProduits(models.Model):
    inspection = models.OneToOneField(InspectionEtablissement, on_delete=models.CASCADE)
    amm = models.CharField(max_length=10, choices=[('oui', 'Oui'), ('non', 'Non')])
    observations_amm = models.TextField(blank=True)
    date_peremption = models.CharField(max_length=10, choices=[('valide', 'Valide'), ('non_valide', 'Non valide')])
    depuis_quand = models.DateField(null=True, blank=True)
    composition = models.TextField(blank=True)
    date_ouverture_flacon = models.CharField(max_length=30, choices=[('mentionn_e', 'Mentionnée'), ('non_mentionn_e', 'Non mentionnée')])
    date_ouverture = models.DateField(null=True, blank=True)
    contenant = models.TextField(blank=True)
    conditionnement = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    deleted_date = models.DateTimeField(null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)


class ConditionsDelivrance(models.Model):
    inspection = models.OneToOneField(InspectionEtablissement, on_delete=models.CASCADE)
    vente_mv = models.CharField(max_length=30, choices=[('sur_ordonnance', 'Sur ordonnance'), ('sans_ordonnance', 'Sans ordonnance'), ('les_deux', 'Les deux')])
    observations_vente = models.TextField(blank=True)
    au_detail = models.CharField(max_length=10, choices=[('oui', 'Oui'), ('non', 'Non')])
    observations_detail = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    deleted_date = models.DateTimeField(null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)


class GestionDechetsBiomedicaux(models.Model):
    inspection = models.OneToOneField(InspectionEtablissement, on_delete=models.CASCADE)
    type_gestion = models.CharField(max_length=30, choices=[
        ('jeter___la_poubelle', 'Jeter à la Poubelle'),
        ('enfouissement', 'Enfouissement'),
        ('incin_ration', 'Incinération'),
        ('recyclage', 'Recyclage'),
        ('autres', 'Autres')
    ])
    autre_type = models.TextField(blank=True)
    observations = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    deleted_date = models.DateTimeField(null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)


class DescriptionLocaux(models.Model):
    inspection = models.OneToOneField(InspectionEtablissement, on_delete=models.CASCADE)
    separation_locaux = models.CharField(max_length=10, choices=[('oui', 'Oui'), ('non', 'Non')])
    quai_debarquement = models.CharField(max_length=10, choices=[('existe', 'Existe'), ('absente', 'Absente')])
    magasins_stockage = models.CharField(max_length=10, choices=[('existe', 'Existe'), ('absente', 'Absente')])
    zone_stockage_retir = models.CharField(max_length=10, choices=[('existe', 'Existe'), ('absente', 'Absente')])
    chambre_froide = models.CharField(max_length=10, choices=[('existente', 'Existente'), ('absente', 'Absente')])
    source_energie = models.CharField(max_length=10, choices=[('oui', 'Oui'), ('non', 'Non')])
    vehicule_transport = models.CharField(max_length=10, choices=[('existente', 'Existente'), ('absente', 'Absente')])
    rayonnage = models.CharField(max_length=10, choices=[('existentes', 'Existentes')])
    observations = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    deleted_date = models.DateTimeField(null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)


class OperationsDistribution(models.Model):
    inspection = models.OneToOneField(InspectionEtablissement, on_delete=models.CASCADE)
    verification_liste_clients = models.CharField(max_length=20, choices=[('fait', 'Fait'), ('non_pas_fait', 'Non fait')])
    respect_fefo = models.CharField(max_length=10, choices=[('oui', 'Oui'), ('non', 'Non')])
    enregistrement_automatique = models.CharField(max_length=20, choices=[('fait', 'Fait'), ('non_pas_fait', 'Non fait')])
    respect_transport = models.CharField(max_length=10, choices=[('oui', 'Oui'), ('non', 'Non')])
    observations = models.TextField(blank=True)
    created_date = models.DateTimeField(auto_now_add=True)
    updated_date = models.DateTimeField(auto_now=True)
    deleted_date = models.DateTimeField(null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)
