from django.urls import path
from .views import ajouter_modifier_conge, liste_conges, supprimer_conge
urlpatterns = [
    path("conges/", liste_conges, name="liste_conges"),
    path("conges/ajouter/", ajouter_modifier_conge, name="ajouter_conge"),
    path("conges/modifier/<int:conge_id>/", ajouter_modifier_conge, name="modifier_conge"),
    path("conges/supprimer/<int:conge_id>/", supprimer_conge, name="supprimer_conge"),
   
    ]
