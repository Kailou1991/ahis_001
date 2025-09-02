from django.urls import path
from . import views

urlpatterns = [
    # Infrastructures
    path('infrastructures/', views.infrastructure_list, name='infrastructure_list'),
    path('infrastructure/create/', views.infrastructure_create, name='infrastructure_create'),
    path('infrastructure/<int:pk>/', views.infrastructure_detail, name='infrastructure_detail'),
    path('infrastructure/<int:pk>/update/', views.infrastructure_update, name='infrastructure_update'),
    path('infrastructure/<int:pk>/delete/', views.infrastructure_delete, name='infrastructure_delete'),

    # Inspections
    path('inspections/', views.inspection_list, name='inspection_list'),
    path('inspection/create/', views.inspection_create, name='inspection_create'),
    path('inspection/<int:pk>/', views.inspection_detail, name='inspection_detail'),
    path('inspection/<int:pk>/update/', views.inspection_update, name='inspection_update'),
    path('inspection/<int:pk>/delete/', views.inspection_delete, name='inspection_delete'),

    # Cartographie et dashboard
    #path('infrastructure/carte/', views.infrastructure_map_view, name='infrastructure_map'),
    path('infrastructure/dashboard/', views.dashboard_infrastructure_view, name='infrastructure_dashboard'),
    path('api/get_etat_precedent/', views.get_etat_precedent, name='get_etat_precedent'),
    path('carte-infrastructures/', views.carte_infrastructure_folium, name='carte_infrastructure'),
    path('export-infrastructures/', views.export_infrastructures_csv, name='export_infrastructures_csv'),
    ]
   
