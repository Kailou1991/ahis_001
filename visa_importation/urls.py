# visa_importation/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path("ajouterFacture/", views.ajouter_facture, name="ajouter_facture"),
    path("listeFacture/", views.liste_factures, name="liste_factures"),
    path("validerFacture/<int:facture_id>/", views.valider_facture_pif, name="valider_facture_pif"),
    path("dashboardFacture/", views.tableau_bord_pif, name="tableau_bord_pif"),
    path("listeNonControle/", views.liste_factures_non_controlees, name="liste_factures_non_controlees"),

]
