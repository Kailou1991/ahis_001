from django.contrib import admin
from .models import FactureImportationVisee

@admin.register(FactureImportationVisee)
class FactureImportationViseeAdmin(admin.ModelAdmin):
    list_display = (
        'numero_facture',
        'date_visa_dsv',
        'vise_par_dsv',
        'est_visa_pif',
        'vise_par_pif',
        'date_visa_pif',
    )
    search_fields = ('numero_facture',)
    list_filter = ('est_visa_pif', 'date_visa_dsv')
