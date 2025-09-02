# alerts/admin.py
from django.contrib import admin
from .models import DestinataireAlerte


@admin.register(DestinataireAlerte)
class DestinataireAlerteAdmin(admin.ModelAdmin):
    list_display = ("email", "nom","formulaire", "actif")
    list_filter = ("actif",)
    search_fields = ("email", "nom")
    ordering = ("-actif", "email")
    list_per_page = 50
    actions = ("activer_selection", "desactiver_selection")

    @admin.action(description="Activer la réception d'alertes pour la sélection")
    def activer_selection(self, request, queryset):
        updated = queryset.update(actif=True)
        self.message_user(request, f"{updated} destinataire(s) activé(s).")

    @admin.action(description="Désactiver la réception d'alertes pour la sélection")
    def desactiver_selection(self, request, queryset):
        updated = queryset.update(actif=False)
        self.message_user(request, f"{updated} destinataire(s) désactivé(s).")
