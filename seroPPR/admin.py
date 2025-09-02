from django.contrib import admin
from .models import (
    resultatAnimal,
    ResultatVillage,
    ResultatCommune,
    ResultatRegion,
    ResultatNational,
)


@admin.register(resultatAnimal)
class resultatAnimalAdmin(admin.ModelAdmin):
    list_display = (
        'numero_animal_preleve', 'espece_prelevee', 'maladie',
        'region', 'commune', 'village',
        'sexe', 'classe_age', 'vaccine', 'marque',
        'resultat_labo', 'densite_optique', 'statut', 'type_enquete'
    )
    list_filter = (
        'maladie', 'region', 'commune', 'village',
        'vaccine', 'marque', 'sexe', 'statut', 'type_enquete'
    )
    search_fields = (
        'numero_animal_preleve', 'espece_prelevee', 'race',
        'maladie', 'commune', 'village'
    )
    ordering = ('type_enquete', 'maladie', 'commune', 'village')


@admin.register(ResultatVillage)
class ResultatVillageAdmin(admin.ModelAdmin):
    list_display = (
        'type_enquete', 'region', 'commune', 'village',
        'positif', 'negatif', 'douteux', 'effectif_preleve_valable', 'prob'
    )
    list_filter = ('type_enquete', 'region', 'commune')
    search_fields = ('village',)


@admin.register(ResultatCommune)
class ResultatCommuneAdmin(admin.ModelAdmin):
    list_display = (
        'type_enquete', 'region', 'commune',
        'somme_prob_village', 'nb_total_village_com',
        'nb_village_echan_com', 'prob_commune'
    )
    list_filter = ('type_enquete', 'region', 'commune')
    search_fields = ('commune',)


@admin.register(ResultatRegion)
class ResultatRegionAdmin(admin.ModelAdmin):
    list_display = (
        'type_enquete', 'region',
        'nb_com_ech', 'nb_com_region',
        'somme_prob_commune_par_region',
        'proportion_poids_region_pays',
        'ponderation_prevalence_relative',
        'variance_relative', 'prevalence_estimee'
    )
    list_filter = ('type_enquete', 'region')
    search_fields = ('region',)


@admin.register(ResultatNational)
class ResultatNationalAdmin(admin.ModelAdmin):
    list_display = (
        'type_enquete',
        'taux_prevalence_nationale', 'erreur_standard',
        'intervalle_confiance_inferieur', 'intervalle_confiance_superieur'
    )
    list_filter = ('type_enquete',)
