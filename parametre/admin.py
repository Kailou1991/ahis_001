# admin.py
from django.contrib import admin
from .models import Ministere, DirectionSV


@admin.register(Ministere)
class MinistereAdmin(admin.ModelAdmin):
    list_display = ("nom", "date_modification")
    search_fields = ("nom",)
    list_filter = ("date_modification",)
    ordering = ("nom",)
    readonly_fields = ("date_modification",)
    fieldsets = (
        (None, {"fields": ("nom",)}),
        ("Métadonnées", {"fields": ("date_modification",), "classes": ("collapse",)}),
    )
    save_on_top = True


@admin.register(DirectionSV)
class DirectionSVAdmin(admin.ModelAdmin):
    list_display = ("nom", "date_modification")
    search_fields = ("nom",)
    list_filter = ("date_modification",)
    ordering = ("nom",)
    readonly_fields = ("date_modification",)
    fieldsets = (
        (None, {"fields": ("nom",)}),
        ("Métadonnées", {"fields": ("date_modification",), "classes": ("collapse",)}),
    )
    save_on_top = True


# En-têtes de l’admin (optionnel)
admin.site.site_header = "Administration AHIS"
admin.site.site_title = "AHIS Admin"
admin.site.index_title = "Tableau de bord d’administration"
