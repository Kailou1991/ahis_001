from django.contrib import admin
from .models import Personnel
from .models import Titre
from .models import Entite

# Register your models here.
admin.site.register(Personnel)
admin.site.register(Titre)
admin.site.register(Entite)