from django.urls import path
from .views import ObjectifStats

app_name = "objectif_sn"

urlpatterns = [
    path("stats_objectifs/", ObjectifStats.as_view(), name="stats_objectifs"),
]
