from django.urls import path
from .views import upload_excel,generer_fichier_modele,dashboard_sero,supprimer_enquete

urlpatterns = [
    path('upload/', upload_excel, name='upload_excel'),
    path('generer-modele/', generer_fichier_modele, name='generer_modele'),
    path('dashboard-sero/', dashboard_sero, name='dashboard_sero'),
    path('supprimer-enquete/', supprimer_enquete, name='supprimer_enquete'),

]
