# materiel/admin.py
from django.contrib import admin
from .models import TypeMateriel, Dotation
from .models import DotationDoseVaccin

@admin.register(TypeMateriel)
class TypeMaterielAdmin(admin.ModelAdmin):
    search_fields = ("nom",)

@admin.register(Dotation)
class DotationAdmin(admin.ModelAdmin):
    list_display = ("date_dotation", "region", "type_materiel", "quantite", "user")
    list_filter = ("region", "type_materiel", "date_dotation")
    search_fields = ("region__Nom", "type_materiel__nom")
    date_hierarchy = "date_dotation"
    ordering = ("-date_dotation",)


@admin.register(DotationDoseVaccin)
class DotationDoseVaccinAdmin(admin.ModelAdmin):
    list_display = ("date_dotation", "campagne", "maladie", "quantite_doses", "user")
    list_filter  = ("campagne", "maladie", "date_dotation")
    search_fields = ("campagne__Campagne", "maladie__Maladie", "observations")
    date_hierarchy = "date_dotation"
