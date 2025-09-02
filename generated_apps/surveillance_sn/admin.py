from django.contrib import admin
from .models import SurveillanceSn, SurveillanceSnChild783b28ae


class SurveillanceSnChild783b28aeInline(admin.TabularInline):
    model = SurveillanceSnChild783b28ae
    extra = 0

@admin.register(SurveillanceSn)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('id', 'ajouter_un_prelevement', 'commentaire_de_la_suspicion', 'commentaire_mesures_de_control', 'end', 'formhub_uuid')
    inlines = [SurveillanceSnChild783b28aeInline]
