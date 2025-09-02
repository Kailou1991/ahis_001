from django.urls import path
from . import views

urlpatterns = [
    path('abattage/', views.liste_abattage, name='liste_abattage'),
    path('abattage/ajouter/', views.ajouter_abattage, name='ajouter_abattage'),
    path('abattage/modifier/<int:pk>/', views.modifier_abattage, name='modifier_abattage'),
    path('abattage/supprimer/<int:pk>/', views.supprimer_abattage, name='supprimer_abattage'),
    path('ante-mortem/', views.liste_ante_mortem, name='liste_ante_mortem'),
    path('ante-mortem/ajouter/', views.ajouter_ante_mortem, name='ajouter_ante_mortem'),
    path('ante-mortem/modifier/<int:pk>/', views.modifier_ante_mortem, name='modifier_ante_mortem'),
    path('ante-mortem/supprimer/<int:pk>/', views.supprimer_ante_mortem, name='supprimer_ante_mortem'),
    path('saisies-totales/', views.liste_saisies_totales, name='liste_saisies_totales'),
    path('saisies-totales/ajouter/', views.ajouter_saisies_totales, name='ajouter_saisies_totales'),
    path('saisies-totales/modifier/<int:pk>/', views.modifier_saisies_totales, name='modifier_saisies_totales'),
    path('saisies-totales/supprimer/<int:pk>/', views.supprimer_saisies_totales, name='supprimer_saisies_totales'),
    path('saisies-organes/', views.liste_saisies_organes, name='liste_saisies_organes'),
    path('saisies-organes/ajouter/', views.ajouter_saisies_organes, name='ajouter_saisies_organes'),
    path('saisies-organes/modifier/<int:pk>/', views.modifier_saisies_organes, name='modifier_saisies_organes'),
    path('saisies-organes/supprimer/<int:pk>/', views.supprimer_saisies_organes, name='supprimer_saisies_organes'),
    path('inspection-viande/', views.liste_inspections_viande, name='liste_inspections_viande'),
    path('inspection-viande/ajouter/', views.ajouter_inspection_viande, name='ajouter_inspection_viande'),
    path('inspection-viande/modifier/<int:pk>/', views.modifier_inspection_viande, name='modifier_inspection_viande'),
    path('inspection-viande/supprimer/<int:pk>/', views.supprimer_inspection_viande, name='supprimer_inspection_viande'),
    path('dashboard-sante-publique/', views.dashboard_sante_publique, name='dashboard_sante_publique'),
    path("export-sante-excel/", views.export_sante_publique_excel, name="export_sante_excel"),


]


