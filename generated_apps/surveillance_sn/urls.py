# generated_apps/surveillance_sn/urls.py
from django.urls import path
from .views import *
from .views_bulletin import generer_bulletin_surv
from .views_dashboard import dashboard_surveillance
from .views_export_map import export_surv_excel


app_name = "surveillance_sn"

urlpatterns = [
    path("stats_surveillance/", SurveillanceStats.as_view(), name="stats_surveillance"),
    path("foyer/<int:pk>/", SurveillanceDetail.as_view(), name="surveillance_detail"),
    path("bulletin_surveillance/", generer_bulletin_surv, name="bulletin_surveillance"),
    path("dashboard_surveillance/", dashboard_surveillance, name="dashboard_surveillance"),
    path("surv_export/", export_surv_excel, name="surv_export"),

]
