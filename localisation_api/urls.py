from django.urls import path
from . import views

urlpatterns = [
    path('departements/', views.get_departements_by_region, name='api_departements_by_region'),
    path('communes/', views.get_communes_by_departement, name='api_communes_by_departement'),
]
