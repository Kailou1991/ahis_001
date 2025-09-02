from django.urls import path
from . import views

urlpatterns = [
    path("ajax/departements/", views.get_departements, name="ajax_get_departements"),
    path("ajax/communes/", views.get_communes, name="ajax_get_communes"),
    path('deplacementanimaux_list', views.deplacementanimaux_list, name='deplacementanimaux_list'),
    path('deplacementanimaux/<int:pk>/', views.deplacementanimaux_detail, name='deplacementanimaux_detail'),
    path('deplacementanimaux/create/', views.deplacementanimaux_create, name='deplacementanimaux_create'),
    path('deplacementanimaux/<int:pk>/update/', views.deplacementanimaux_update, name='deplacementanimaux_update'),
    path('deplacementanimaux/<int:pk>/delete/', views.deplacementanimaux_delete, name='deplacementanimaux_delete'),
    path('deplacementanimaux_dashbord', views.tableau_de_bord, name='deplacementanimaux_dashbord'),
     path('export/deplacement_animaux/', views.export_deplacement_animaux_xls, name='export_deplacement_animaux_xls'),
]
