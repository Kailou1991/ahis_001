from django.db import models
from django.contrib.auth.models import User
from Region.models import Region 
from Espece.models import Espece
from Departement.models import Departement
from Commune.models import Commune
from Maladie.models import Maladie 

class DeplacementAnimal(models.Model):
    class ModeTransport(models.TextChoices):
        ROUTE = 'ROUTE', 'Route'
        AIR = 'AIR', 'Air'
        MER = 'MER', 'Mer'
        RAIL = 'RAIL', 'Rail'

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name="Enregistré par")
    
    espece = models.ForeignKey(Espece, on_delete=models.PROTECT, verbose_name="Espèce concernée")
    nombre_animaux = models.PositiveIntegerField("Nombre d’animaux")
    
    # Localisation
    region_provenance = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, related_name='deplacement_sortie')
    departement_provenance = models.ForeignKey(Departement, on_delete=models.SET_NULL, null=True, related_name='deplacement_sortie')
    commune_provenance = models.ForeignKey(Commune, on_delete=models.SET_NULL, null=True, related_name='deplacement_sortie')

    region_destination = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, related_name='deplacement_entree')
    departement_destination = models.ForeignKey(Departement, on_delete=models.SET_NULL, null=True, related_name='deplacement_entree')
    commune_destination = models.ForeignKey(Commune, on_delete=models.SET_NULL, null=True, related_name='deplacement_entree')

    etablissement_origine = models.CharField("Établissement d'origine", max_length=255, blank=True, null=True)
    etablissement_destination = models.CharField("Établissement de destination", max_length=255, blank=True, null=True)

    date_deplacement = models.DateField("Date effective du déplacement")
    duree_deplacement = models.PositiveIntegerField("Durée du déplacement (en jours)", null=True, blank=True)

    mode_transport = models.CharField("Mode de transport", max_length=10, choices=ModeTransport.choices, default=ModeTransport.ROUTE)
    raison_deplacement = models.TextField("Motif du déplacement", blank=True, null=True)

  # Nouveaux champs liés aux documents contrôlés / délivrés
    nombre_certificats_vaccination_controles = models.PositiveIntegerField("Certificats de vaccination contrôlés", null=True, blank=True)
    nombre_certificats_vaccination_delivres = models.PositiveIntegerField("Certificats de vaccination délivrés", null=True, blank=True)
    nombre_laisser_passer_controles = models.PositiveIntegerField("Laisser-passer contrôlés", null=True, blank=True)
    nombre_laisser_passer_delivres = models.PositiveIntegerField("Laisser-passer délivrés", null=True, blank=True)

    # Propriétaire
    nom_proprietaire = models.CharField("Nom du propriétaire", max_length=255)
    contact_proprietaire = models.CharField("Téléphone du propriétaire", max_length=20)

    # Transporteur
    nom_transporteur = models.CharField("Nom du transporteur", max_length=255, blank=True)
    contact_transporteur = models.CharField("Téléphone du transporteur", max_length=20, blank=True)
 
    # --- Surveillance sanitaire liée au déplacement ---
    CHOIX_OUI_NON = [
    ('OUI', 'OUI'),
    ('NON', 'NON'),
]
    maladie_detectee = models.CharField(
        "Y a-t-il une maladie suspectée ?",
        max_length=3,
        choices=CHOIX_OUI_NON,
        default='NON'
    )

    maladie_suspectee = models.ForeignKey(
        Maladie,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Maladie suspectée / constatée",
        help_text="Sélectionner la maladie suspectée ou détectée"
    )
    nombre_animaux_malades = models.PositiveIntegerField(
        "Nombre d’animaux malades", blank=True, null=True
    )
    nombre_animaux_traites = models.PositiveIntegerField(
        "Nombre d’animaux traités", blank=True, null=True
    )
    nombre_animaux_vaccines = models.PositiveIntegerField(
        "Nombre d’animaux vaccinés", blank=True, null=True
    )
    nombre_animaux_quarantaine = models.PositiveIntegerField(
        "Nombre d’animaux mis en quarantaine", blank=True, null=True
    )
    mesures_prises = models.TextField(
        "Mesures de gestion sanitaire", blank=True, null=True,
        help_text="Autres actions : désinfection, isolement, alerte sanitaire..."
    )

        # Coordonnées GPS du poste de contrôle
    latitude_poste_controle = models.FloatField(
        "Latitude du poste de contrôle", null=True, blank=True,
        help_text="Coordonnée latitude du poste de contrôle (ex: 13.51234)"
    )
    longitude_poste_controle = models.FloatField(
        "Longitude du poste de contrôle", null=True, blank=True,
        help_text="Coordonnée longitude du poste de contrôle (ex: 2.13245)"
    )

    # Suivi
    date_enregistrement = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Déplacement d’animaux"
        verbose_name_plural = "Déplacements d’animaux"
        ordering = ['-date_deplacement']

    def __str__(self):
        return f"{self.nombre_animaux} {self.espece} déplacés ({self.commune_provenance} → {self.commune_destination})"

