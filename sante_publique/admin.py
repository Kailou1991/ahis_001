from django.contrib import admin
from .models import (
    RegistreAbattage,
    RegistreInspectionAnteMortem,
    RegistreSaisiesTotales,
    RegistreSaisiesOrganes,
    InspectionViande  # si tu as aussi intégré ce modèle
)


@admin.register(RegistreAbattage)
class RegistreAbattageAdmin(admin.ModelAdmin):
    list_display = ('espece', 'commune', 'nombres', 'poids', 'valeur_financiere', 'date_enregistrement')
    list_filter = ('region', 'departement', 'commune', 'espece')
    search_fields = ('observations',)


@admin.register(RegistreInspectionAnteMortem)
class RegistreInspectionAnteMortemAdmin(admin.ModelAdmin):
    list_display = ('espece', 'commune', 'nombres', 'poids', 'valeur_financiere', 'date_enregistrement')
    list_filter = ('region', 'departement', 'commune', 'espece')
    search_fields = ('anomalies', 'symptomes', 'observations')


@admin.register(RegistreSaisiesTotales)
class RegistreSaisiesTotalesAdmin(admin.ModelAdmin):
    list_display = ('espece', 'commune', 'nombres', 'poids', 'valeur_financiere', 'date_enregistrement')
    list_filter = ('region', 'departement', 'commune', 'espece')
    search_fields = ('motifs_saisies', 'observations')


@admin.register(RegistreSaisiesOrganes)
class RegistreSaisiesOrganesAdmin(admin.ModelAdmin):
    list_display = ('espece', 'commune', 'nombres', 'poids', 'valeur_financiere', 'date_enregistrement')
    list_filter = ('region', 'departement', 'commune', 'espece')
    search_fields = ('organes_saisis', 'motifs_saisies_organes', 'observations')


# (Optionnel) Si le modèle InspectionViande est aussi intégré
try:
    from .models import InspectionViande

    @admin.register(InspectionViande)
    class InspectionViandeAdmin(admin.ModelAdmin):
        list_display = ('abattoir', 'espece', 'etat_animal', 'aspect_carcasse', 'date_inspection')
        list_filter = ('espece', 'etat_animal', 'aspect_carcasse')
        search_fields = ('inspecteur', 'description_anomalies', 'observations')
except ImportError:
    pass
