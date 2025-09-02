from django.contrib import admin
from .models import VaccinationSn, VaccinationSnChild0c8ff1d1


class VaccinationSnChild0c8ff1d1Inline(admin.TabularInline):
    model = VaccinationSnChild0c8ff1d1
    extra = 0

@admin.register(VaccinationSn)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('id', 'campagne', 'commentaire', 'datesaisie', 'end', 'formhub_uuid')
    inlines = [VaccinationSnChild0c8ff1d1Inline]
