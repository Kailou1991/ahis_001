from django.urls import path
from . import views

urlpatterns = [
    path('campagnes/', views.liste_campagnes, name='liste_campagnes'),
    path('campagne/fermer/<int:id>/', views.fermer_campagne, name='fermer_campagne'),
    path('get_type_campagne/', views.get_type_campagne, name='get_type_campagne'),
    path('campagne/ajouter/', views.ajouter_campagne, name='ajouter_campagne'),
    path('campagne/supprimer/<int:id>/', views.supprimer_campagne, name='supprimer_campagne'),


]

