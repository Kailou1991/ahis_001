from django.urls import path
from . import views

urlpatterns = [
    path('personnel_list', views.personnel_list, name='personnel_list'),
    path('personnel_detail/<int:pk>/', views.personnel_detail, name='personnel_detail'),
    path('personnel/create/', views.personnel_create, name='personnel_create'),
    path('personnel/update/<int:pk>/', views.personnel_update, name='personnel_update'),
    path('personnel/delete/<int:pk>/', views.personnel_delete, name='personnel_delete'),
    path('personnel/create/get_departements/', views.get_departements, name='get_departements'),
    path('personnel/create/get_communes/',views.get_communes, name='get_communes'),
    path('dashboard_personnel', views.dashboard_personnel, name='dashboard_personnel'),
    path('api/region/', views.add_region, name='add_region'),
    path('api/departement/', views.add_departement, name='add_departement'),
    path('api/commune/', views.add_commune, name='add_commune'),
    path('api/titre/', views.add_titre, name='add_titre'),
    path('api/entite/', views.add_entite, name='add_entite'), 

]
