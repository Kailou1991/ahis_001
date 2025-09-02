from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import UserProfile

# Inline pour lier UserProfile au modèle User
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profiles'

# Personnalisation de UserAdmin pour inclure UserProfile
class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)

# Ré-enregistrement du modèle User avec le nouvel admin personnalisé
admin.site.unregister(User)
admin.site.register(User, UserAdmin)
