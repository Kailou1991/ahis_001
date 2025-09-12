from django.contrib import admin
from .models import DeplacementAnimal
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
   