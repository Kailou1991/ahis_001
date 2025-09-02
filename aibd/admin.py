from django.contrib import admin
from .models import ServiceVeterinaireAIBD, Continent, PaysMonde

admin.site.register(Continent)
admin.site.register(PaysMonde)
admin.site.register(ServiceVeterinaireAIBD)
