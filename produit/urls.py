from django.urls import path
from . import views

urlpatterns = [
    path('enregistrements/', views.produit_list, name='produit_list'),
    path('api/produit/<int:produit_id>/', views.get_produit_details, name='get_produit_details'),
    path('enregistrements/<int:pk>/', views.produit_detail, name='produit_detail'),
    path('enregistrements/create/', views.enregistrement_create, name='produit_create'),
    path('enregistrements/<int:pk>/edit/', views.produit_update, name='produit_update'),
    path('enregistrements/<int:pk>/delete/', views.produit_delete, name='produit_delete'),
    path('api/produit/',views.add_produit, name='add_produit'),
    path('api/produit/', views.add_produit, name='add_produit'),
    path('api/partenaire/', views.add_partenaire, name='add_partenaire'),
    path('api/firme/', views.add_firme, name='add_firme'),
    path('api/structure_import/', views.add_structure_import, name='add_structure_import'),
    path('api/structure_export/', views.add_structure_export, name='add_structure_export'),
    path('dashboard-produit/', views.dashboard_produit, name='dashboard_produit'),
    path('export/', views.export_enregistrements_excel, name='export_enregistrements_excel'),
    ##Produit
    path('produits/create/', views.produitVet_create, name='produitVet_create'),
    path('produits/<int:pk>/', views.produitVet_detail, name='produitVet_detail'),
    path('produits/<int:pk>/edit/', views.produitVet_update, name='produitVet_update'),
    path('produits/<int:pk>/delete/', views.produitVet_delete, name='produitVet_delete'),
    path('produits/', views.produitVet_list, name='produitVet_list'),
    path('export/excel/', views.export_produitsVet_excel, name='export_produitsVet_excel'),
    
    
   


]



