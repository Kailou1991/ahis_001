# admin.py
from django.contrib import admin
from .models import Direction, SousDirection, Poste, Grade, Echelon, Employe, HistoriqueCarriere, Formation
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune

# Enregistrement des modèles dans l'admin
class DirectionAdmin(admin.ModelAdmin):
    list_display = ('nom', 'get_type_display')  # Afficher le type sous forme lisible
    search_fields = ('nom',)
    list_filter = ('type',)  # Ajouter un filtre par type de direction
    
    def get_type_display(self, obj):
        return obj.get_type_display()  # Afficher 'Générale' ou 'Technique'
    get_type_display.admin_order_field = 'type'  # Permet de trier par type
    get_type_display.short_description = 'Type de Direction'


class SousDirectionAdmin(admin.ModelAdmin):
    list_display = ('nom', 'direction')
    search_fields = ('nom',)
    list_filter = ('direction',)


class PosteAdmin(admin.ModelAdmin):
    list_display = ('nom', 'commune', 'departement', 'region', 'date_creation', 'statut', 'direction', 'sous_direction')
    search_fields = ('nom', 'commune__nom', 'departement__nom', 'region__nom', 'direction__nom', 'sous_direction__nom')
    list_filter = ('statut', 'direction', 'sous_direction', 'commune', 'departement', 'region')


class GradeAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)


class EchelonAdmin(admin.ModelAdmin):
    list_display = ('nom', 'description')
    search_fields = ('nom',)


class EmployeAdmin(admin.ModelAdmin):
    list_display = ('matricule', 'nom', 'prenom', 'date_naissance', 'sexe', 'telephone', 'email', 'date_embauche', 'poste', 'position', 'grade', 'echelon')
    search_fields = ('matricule', 'nom', 'prenom', 'telephone', 'email')
    list_filter = ('position', 'grade', 'echelon', 'poste')


class HistoriqueCarriereAdmin(admin.ModelAdmin):
    list_display = ('employe', 'poste', 'date_debut', 'date_fin', 'type_changement', 'remarque')
    search_fields = ('employe__nom', 'poste__nom', 'type_changement')
    list_filter = ('type_changement',)


class FormationAdmin(admin.ModelAdmin):
    list_display = ('employe', 'intitule', 'institution', 'date_debut', 'date_fin', 'diplome_obtenu')
    search_fields = ('employe__nom', 'intitule', 'institution')
    list_filter = ('employe',)


# Enregistrement des classes dans l'admin
admin.site.register(Direction, DirectionAdmin)
admin.site.register(SousDirection, SousDirectionAdmin)
admin.site.register(Poste, PosteAdmin)
admin.site.register(Grade, GradeAdmin)
admin.site.register(Echelon, EchelonAdmin)
admin.site.register(Employe, EmployeAdmin)
admin.site.register(HistoriqueCarriere, HistoriqueCarriereAdmin)
admin.site.register(Formation, FormationAdmin)
