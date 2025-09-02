from django.contrib import admin
from .models import FormulaireKobo, SyncLog

@admin.register(FormulaireKobo)
class FormulaireKoboAdmin(admin.ModelAdmin):
    list_display = ("nom", "uid", "parser", "modele_django", "actif")

@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ("formulaire", "date_sync", "status", "message")
