from django.contrib import admin
from .models import Infrastructure,TypeInfrastructure,TypeFinancement,EtatInfrastructure,Inspection,HistoriqueEtatInfrastructure

# Register your models here.
admin.site.register(Infrastructure)
admin.site.register(TypeInfrastructure)
admin.site.register(TypeFinancement)
admin.site.register(EtatInfrastructure)
admin.site.register(Inspection)
admin.site.register(HistoriqueEtatInfrastructure)