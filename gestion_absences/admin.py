from django.contrib import admin
from .models import TypeConge, Conge, Employe

# Enregistrement des modèles dans l'admin

@admin.register(TypeConge)
class TypeCongeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description', 'nombreJour')
    search_fields = ('nom',)
    list_filter = ('nom',)

@admin.register(Conge)
class CongeAdmin(admin.ModelAdmin):
    list_display = ('employe', 'type_conge', 'date_debut', 'date_fin', 'duree','solde', 'statut','remarque')
    search_fields = ('employe__nom', 'employe__prenom', 'type_conge__nom', 'statut')
    list_filter = ('type_conge', 'statut', 'date_debut', 'date_fin')
    date_hierarchy = 'date_debut'
    raw_id_fields = ('employe', 'type_conge')