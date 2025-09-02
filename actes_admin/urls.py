from django.urls import path
from . import views

urlpatterns = [
    # Soumission de la demande
    path('soumettre/', views.soumettre_demande, name='soumettre_demande'),
    path('soumettre_public/', views.soumettre_demande_public, name='soumettre_demande_public'),
    # Upload du document signé (accessible au niveau central)
    path('document-signe/<int:demande_id>/', views.uploader_document_final, name='uploader_document_final'),
    path('demandes/', views.liste_demandes, name='liste_demandes'),
    path('ajax/load-actes/', views.load_actes, name='ajax_load_actes'),
    path('details/<int:pk>/', views.details_acte, name='details_acte'),
    path('affecter/<int:pk>/', views.affecter_demande, name='affecter_demande'),
    path('relancer/<int:pk>/<str:niveau>/', views.relancer_niveau, name='relancer_niveau'),
    path('suivi/<int:pk>/', views.suivi_et_traitement_demande, name='suivi_et_traitement_demande'),
    path('dashboard-actes/', views.tableau_de_bord, name='tableau_de_bord_actes'),
    path("centre-aide-documents/", views.centre_aide_documents, name="centre_aide_documents"),



]
