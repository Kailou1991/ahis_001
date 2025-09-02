from django.db import models
from django.contrib.auth.models import User
from Maladie.models import Maladie
from Region.models import Region
from Espece.models import Espece
from Departement.models import Departement
from Commune.models import Commune
from Laboratoire.models import Laboratoire
from TypeTestLabo.models import TypeTestLabo
from multiselectfield import MultiSelectField

class Foyer(models.Model):
    VACCINATION_CHOICES = [('OUI', 'Oui'), ('NON', 'Non')]
    RESULTAT_LABO_CHOICES = [('OUI', 'Oui'), ('NON', 'Non')]

    RESULTAT_TRI_CHOICES = [
        ('positif', 'Positif'),
        ('negatif', 'Négatif'),
        ('douteux', 'Douteux'),
    ]

    LIEU_SUSPICION_CHOICES = [
        ('abattoir', 'Abattoir'),
        ('aire_abattage', 'Aire d\'abattage'),
        ('ferme_clinique', 'Troupeau/Ferme/Clinique'),
    ]

    SERVICE_LABO_CHOICES = [
        ('serologie', 'Sérologie'),
        ('bacteriologie', 'Bactériologie'),
        ('virologie', 'Virologie'),
        ('autre', 'Autre'),
    ]

    NATURE_PRELEVEMENT_CHOICES = [
        ('ecouvillon_buccal', 'Écouvillon buccal'),
        ('ecouvillon_nasal', 'Écouvillon nasal'),
        ('ecouvillon_oculaire', 'Écouvillon oculaire'),
        ('ecouvillon_rectal', 'Écouvillon rectal'),
        ('ecouvillon_cloacal', 'Écouvillon cloacal (volailles)'),
        ('sang_total', 'Sang total'),
        ('serum', 'Sérum'),
        ('plasma', 'Plasma'),
        ('urine', 'Urine'),
        ('fèces', 'Fèces'),
        ('tissu_organe', 'Tissu / Organe'),
        ('ganglion', 'Ganglion lymphatique'),
        ('poumon', 'Poumon'),
        ('foie', 'Foie'),
        ('tete', 'Tête'),
        ('lba', 'LBA (Lavage Broncho-Alvéolaire)'),
        ('liquide_cephalo_rachidien', 'Liquide céphalo-rachidien'),
        ('lait', 'Lait'),
        ('contenu_digestif', 'Contenu digestif'),
        ('contenu_respiratoire', 'Contenu respiratoire'),
        ('os', 'Os'),
        ('peau', 'Peau / Lésions cutanées'),
        ('autre', 'Autre (à préciser)'),
    ]

    MESURE_CONTROLE_CHOICES = [
        ('abattage_sanitaire', 'Abattage sanitaire'),
        ('mise_a_mort_selective', 'Mise à mort sélective'),
        ('mise_en_quarantaine', 'Mise en quarantaine'),
        ('vaccination_en_reponse', 'Vaccination en réponse au foyer'),
        ('traitement', 'Traitement curatif'),
        ('desinfection', 'Désinfection des locaux'),
        ('desinsectisation', 'Désinsectisation'),
        ('deratisation', 'Dératisation'),
        ('interdiction_mouvement', 'Interdiction des mouvements d’animaux'),
        ('limitation_acces_zone', 'Limitation d’accès à la zone infectée'),
        ('sensibilisation_elevecs', 'Sensibilisation des éleveurs'),
        ('surveillance_renforcee', 'Surveillance renforcée'),
        ('controle_post_vaccination', 'Contrôle post-vaccination'),
        ('elim_residus_contamines', 'Élimination des résidus contaminés'),
        ('fermeture_marche_animaux', 'Fermeture temporaire des marchés à bétail'),
        ('autre', 'Autre mesure (à préciser)'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    date_signalement = models.DateField(null=True, blank=True, help_text="Date à laquelle le foyer a été signalé")

    date_rapportage = models.DateField(null=True)
    espece = models.ForeignKey(Espece, on_delete=models.CASCADE)
    maladie = models.ForeignKey(Maladie, on_delete=models.CASCADE)
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    departement = models.ForeignKey(Departement, on_delete=models.CASCADE)
    commune = models.ForeignKey(Commune, on_delete=models.CASCADE)
    localite = models.CharField(max_length=255)
    lieu_suspicion = models.CharField(max_length=255, choices=LIEU_SUSPICION_CHOICES, default='ferme_clinique')
    nom_lieu_suspicion = models.CharField(max_length=255, blank=True, null=True)
    longitude = models.FloatField(null=True, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    effectif_troupeau = models.IntegerField(default=0)
    nbre_sujets_malade = models.IntegerField(null=True, blank=True)
    nbre_sujets_morts = models.IntegerField(null=True, blank=True)
    nbre_des_cas_de_morsure_humains = models.IntegerField(null=True, blank=True)
    nbre_des_cas_de_morsure_animaux = models.IntegerField(null=True, blank=True)

    mesure_controle = MultiSelectField(choices=MESURE_CONTROLE_CHOICES, blank=True, null=True)
    nbre_sujets_traites = models.IntegerField(null=True, blank=True)
    nbre_sujets_vaccines = models.IntegerField(null=True, blank=True)
    nbre_sujets_en_quarantaine = models.IntegerField(null=True, blank=True)
    nbre_sujets_abattus = models.IntegerField(null=True, blank=True)

    vaccinations_recentes = models.CharField(max_length=3, choices=VACCINATION_CHOICES, default='NON')
    maladie_vaccination = models.ForeignKey(Maladie, on_delete=models.SET_NULL, null=True, blank=True, related_name='maladie_vaccination')
    date_vaccination = models.DateField(null=True, blank=True)

    nature_prelevement = models.CharField(choices=NATURE_PRELEVEMENT_CHOICES)
    nbre_echant_recu = models.IntegerField(null=True, blank=True)
    #nbre_echant_positif = models.IntegerField(null=True, blank=True)
    nbre_echant_inexploitable = models.IntegerField(null=True, blank=True)
    #nbre_echant_nonconforme = models.IntegerField(null=True, blank=True)

    prelevement_envoye = models.CharField(max_length=3, choices=RESULTAT_LABO_CHOICES, default='NON')
    resultat_laboratoire = models.CharField(max_length=3, choices=RESULTAT_LABO_CHOICES, default='NON')
    date_envoi_prelevement = models.DateField(null=True, blank=True)
    date_reception_prelevement = models.DateField(null=True, blank=True)
    date_resultat = models.DateField(null=True, blank=True)
     # NOUVELLES modalités
    resultat_analyse = models.CharField(
        max_length=8, choices=RESULTAT_TRI_CHOICES, null=True, blank=True,
        help_text="Positif / Négatif / Douteux"
    )
    laboratoire = models.ForeignKey(Laboratoire, blank=True, null=True, on_delete=models.CASCADE)
    type_test_labo = models.ForeignKey(TypeTestLabo, blank=True, null=True, on_delete=models.CASCADE)
    service_labo = models.CharField(max_length=50, choices=SERVICE_LABO_CHOICES, null=True, blank=True)
    absence_reactifs = models.CharField(max_length=3, choices=RESULTAT_LABO_CHOICES, default='OUI')
    recommandations = models.TextField(blank=True, null=True)
    fichier_resultat = models.FileField(upload_to='resultats_labo/', null=True, blank=True)
    chiffre_kbt = models.BooleanField(default=False)
    idkobo = models.CharField(max_length=255, blank=True, null=True)
    notification_envoyee = models.BooleanField(
        default=False,
        help_text="Indique si la notification e-mail a déjà été envoyée."
    )

    def __str__(self):
        return f"Foyer - {self.localite} ({self.date_rapportage})"
    
