from django.urls import path
from . import views
from django.urls import include
from rest_framework.routers import DefaultRouter
from .views import FoyerViewSet



router = DefaultRouter()
router.register(r'foyer', FoyerViewSet)


urlpatterns = [
    path('foyer_list', views.foyer_list, name='foyer_list'),
    path('foyer_create/', views.foyer_create, name='foyer_create'),
    path('foyer_update/<int:pk>/', views.foyer_update, name='foyer_update'),
    path('foyer_delete/<int:pk>/', views.foyer_delete, name='foyer_delete'),
    path('foyer_create/get_departements/', views.get_departements, name='get_departements'),
    path('foyer_create/get_communes/', views.get_communes, name='get_communes'),
    path('foyer_create/get_maladies/', views.get_maladies, name='get_maladies'),
    path('import_foyer/', views.import_foyer_data, name='import_foyer'),
    path('foyer/<int:pk>/', views.detail_foyer, name='detail_foyer'),
    path('foyer_create/get_maladie_type/', views.get_maladie_type, name='get_maladie_type'),
    path('bulletin', views.generer_bulletin, name='bulletin'),
    path('dashboardFoyer', views.dashboardFoyer, name='dashboardFoyer'),
    path('export_foyer_excel', views.export_foyer_excel, name='export_foyer_excel'),
    
    
    
    ##API
    #path('api/foyer/', include(router.urls)),


]
