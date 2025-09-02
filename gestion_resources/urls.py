# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('employes/', views.liste_employes, name='liste_employes'),
    path('employe/<int:employe_id>/', views.detail_employe, name='detail_employe'),
    path('employe/ajouter/', views.ajouter_modifier_employe, name='ajouter_employe'),
    path('employe/<int:employe_id>/carrieres/', views.historique_carriere, name='carrieres'),
    path('employe/<int:employe_id>/mettre_a_jour_document/', views.mettre_a_jour_document, name='mettre_a_jour_document'),
    path('employe/modifier/<int:employe_id>/', views.ajouter_modifier_employe, name='modifier_employe'),
    path('tableau-de-bord/', views.tableau_de_bord, name='tableau_de_bord_personnel'),
    path('historique/supprimer/<int:historique_id>/', views.supprimer_historique, name='supprimer_historique'),
    path('document/supprimer/<int:document_id>/', views.supprimer_document, name='supprimer_document'),
    path('employe/<int:employe_id>/formations/', views.formations_employe, name='formations_employe'),
    path('formation/supprimer/<int:formation_id>/', views.supprimer_formation, name='supprimer_formation'),
    path('tableau-de-bord-central/', views.tableau_de_bord_central, name='tableau_de_bord_central'),
    path('tableau-de-bord-regional/', views.tableau_de_bord_regional, name='tableau_de_bord_regional'),
    
]
