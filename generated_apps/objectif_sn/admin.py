from django.contrib import admin
from .models import ObjectifSn, ObjectifSnChild0c8ff1d1


class ObjectifSnChild0c8ff1d1Inline(admin.TabularInline):
    model = ObjectifSnChild0c8ff1d1
    extra = 0

@admin.register(ObjectifSn)
class ParentAdmin(admin.ModelAdmin):
    list_display = ('id', 'campagne', 'end', 'formhub_uuid', 'grp4_departement', 'grp4_region')
    inlines = [ObjectifSnChild0c8ff1d1Inline]
