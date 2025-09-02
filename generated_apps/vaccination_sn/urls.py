from django.urls import path
from .views import *


app_name = "vaccination_sn"
urlpatterns = [
    # ... tes autres routes ...
    path("modules/vaccination_sn/stats/", VaccinationStats.as_view(), name="stats"),
    
    path("api/departements/", DepartementsForRegion.as_view(), name="api_departements"),
    path("vaccination_dashboard/", KoboDashboardView.as_view(), name="vaccination_dashboard"),
     path('rapport_camvac/', camvac_excel, name='rapport_camvac'),
     
]
