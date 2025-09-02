
from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
       
]

# accounts/urls.py
from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    system_admin_view,
    regional_admin_view,
    departemental_admin_view,
    animateur_admin_view,
    dsa_admin_view,
    medicament_admin_view,
    superviseur_admin_view,
    public_admin_view,
    rh_admin_view,
    agent_suivi_admin_view,
    login_view,
    register_view,
    logout_view,
    dashboard_general,
    aibd_admin_view,
    santePublique_admin_view,
    receptioniste_admin_view,
    analyste_admin_view,
    directeurlbao_admin_view,
    

    
    #dashbord_view,
   
    

)

urlpatterns = [
    path('', login_view, name='login'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='index.html'), name='login'),
    path('system-admin/', system_admin_view, name='system_admin'),
    path('regional-admin/', regional_admin_view, name='regional_admin'),
    path('departemental-admin/', departemental_admin_view, name='departemental_admin'),
    path('animateur-admin/', animateur_admin_view, name='animateur_admin'),
    path('dsa-admin/', dsa_admin_view, name='dsa_admin'),
    path('medicament-admin/', medicament_admin_view, name='medicament_admin'),
    path('aibd-admin/', aibd_admin_view, name='aibd_admin'),
    path('santePublique_admin/', santePublique_admin_view, name='santePublique_admin'),
    
    path('superviseur-admin/', superviseur_admin_view, name='superviseur_admin'),
    path('public-admin/', public_admin_view, name='public_admin'),
    path('rh-admin/', rh_admin_view, name='rh_admin'),
    path('agent_suivi-admin/', agent_suivi_admin_view, name='agent_suivi_admin'),
    path('register/', register_view, name='register'),
    path('accounts/logout/', logout_view, name='logout'),
    path('', dashboard_general, name='dashboard_general'),

    ##############labo
    
    path('receptioniste_admin/', receptioniste_admin_view, name='receptioniste_admin'),
    path('analyste_admin/', analyste_admin_view, name='analyste_admin'),
     path('directeurlbao_admin/', directeurlbao_admin_view, name='directeurlbao_admin'),


 
]
