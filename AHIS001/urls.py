from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
   
    path("admin/", admin.site.urls),
    path('', include('data_initialization.urls')),
    path('accounts/', include('django.contrib.auth.urls')),  # Inclure les URL de gestion des utilisateurs
    #path('api/foyer/', include('Foyer.urls')),
    #path('api/chiffrevaccination/', include('ChiffreVaccination.urls')),
    path('', include('Foyer.urls')),
    path('', include('DeplacementAnimaux.urls')),
    path('', include('Infrastructure.urls')),
    path('', include('Personnel.urls')),
    path('', include('produit.urls')),
    path('', include('Document.urls')),
    path('', include('gestion_resources.urls')),
    path('', include('gestion_absences.urls')),
    path('', include('Campagne.urls')),
    path('', include('seroPPR.urls')),
    path('', include('actes_admin.urls')),
    path('api/', include('localisation_api.urls')),
    path('', include('sante_publique.urls')),
    path('', include('inspection_medicaments.urls')),
    path('', include('aibd.urls')),
    path("", include("visa_importation.urls")),
    path("", include("materiel.urls")),
    path('kobo/', include('kobo_integration.urls')),
    #path('modules/', include('generated_apps.urls')),
    path('modules/vaccination_sn/', include('generated_apps.vaccination_sn.urls', namespace='vaccination_sn')),
    path('modules/objectif_sn/', include('generated_apps.objectif_sn.urls', namespace='objectif_sn')),
    path("modules/surveillance_sn/", include("generated_apps.surveillance_sn.urls")),
    path("", include("lims.urls")),
    

    
    ]

# Ajout de la gestion des fichiers statiques en mode développement
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
