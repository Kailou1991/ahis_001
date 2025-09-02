from django.contrib import admin
from .models import Document
from .models import Employe

# Enregistrement du modèle Document dans l'admin
@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('employe', 'nom', 'type_document', 'date_ajout', 'fichier')
    search_fields = ('employe__nom', 'employe__prenom', 'nom', 'type_document')
    list_filter = ('type_document', 'date_ajout')
    date_hierarchy = 'date_ajout'
    raw_id_fields = ('employe',)
    readonly_fields = ('date_ajout',)
