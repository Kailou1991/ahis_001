from django.contrib import admin
from .models import DeplacementAnimal
from Foyer.models import Foyer  # adapte si besoin
from datetime import date

@admin.register(DeplacementAnimal)
class DeplacementAnimalAdmin(admin.ModelAdmin):
    list_display = (
        'date_deplacement', 'espece', 'nombre_animaux', 'commune_provenance',
        'commune_destination', 'mode_transport', 'maladie_suspectee', 'has_maladie'
    )
    list_filter = (
        'region_destination', 'departement_destination', 'espece',
        'maladie_suspectee', 'mode_transport'
    )
    search_fields = ('numero_certificat', 'nom_proprietaire', 'contact_proprietaire')
    actions = ['creer_foyer_depuis_deplacement']

    def has_maladie(self, obj):
        return obj.maladie_suspectee is not None
    has_maladie.boolean = True
    has_maladie.short_description = "Maladie détectée ?"

    @admin.action(description="Créer un foyer à partir du déplacement")
    def creer_foyer_depuis_deplacement(self, request, queryset):
        n = 0
        for deplacement in queryset:
            if deplacement.maladie_suspectee:
                Foyer.objects.create(
                    date_rapportage=date.today(),
                    maladie=deplacement.maladie_suspectee,
                    espece=deplacement.espece,
                    region=deplacement.region_destination,
                    departement=deplacement.departement_destination,
                    commune=deplacement.commune_destination,
                    localite=deplacement.etablissement_destination or "Non renseigné",
                    nbre_sujets_malade=deplacement.nombre_animaux_malades or 0,
                    nbre_sujets_traite=deplacement.nombre_animaux_traites or 0,
                    nbre_sujets_vaccines=deplacement.nombre_animaux_vaccines or 0,
                    nbre_sujets_en_quarintaines=deplacement.nombre_animaux_quarantaine or 0,
                    mesure_controle=deplacement.mesures_prises or "RAS",
                    source_signalement="Déplacement",
                    remarque="Foyer généré depuis déplacement animal"
                )
                n += 1
        self.message_user(request, f"{n} foyer(s) généré(s) avec succès.")
