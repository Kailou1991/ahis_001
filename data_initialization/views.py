
import re
from django.db.models import Sum, F, ExpressionWrapper, FloatField

from .formstatVac import FiltreStatistiquesForm
from django.db.models import Sum, F
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from .decorators import group_required
from django.contrib.auth import authenticate, login as auth_login
import logging
import requests
import json
import math
from django.shortcuts import render
import folium
from folium.plugins import MarkerCluster
import matplotlib.cm as cm
import matplotlib.colors as mcolors
from django.http import JsonResponse
from Campagne.models import Campagne
from Maladie.models import Maladie
from Espece.models import Espece

from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune
from Infrastructure.models import Infrastructure

###utilsation des vues pour le dashbord global
from DeplacementAnimaux.views import*
from Infrastructure.views import*
from Personnel.views import*
from produit.views import*
from actes_admin.views import liste_demandes
from aibd.views import dashboard_aibd
from sante_publique.views import dashboard_sante_publique
from lims.views_demandes import demandes_list
from lims.views_dashboard import dashboard
from lims.views import demandes_list_affectees

from datetime import timedelta
from typing import Optional, List, Dict

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, F, IntegerField
from django.db.models.functions import Coalesce, Trim
from django.shortcuts import render
from django.utils import timezone

from lims.models import (
    Demande,
    Echantillon,
)
from Region.models import Region
from Departement.models import Departement # FK utilisés par LIMS.Demande


def _period(request):
    """Récupère la période via ?days= (défaut 30j)."""
    end = timezone.now()
    try:
        days = int(request.GET.get("days", 30))
    except Exception:
        days = 30
    start = end - timedelta(days=max(1, days))
    return start, end, days


@login_required
def dashboard_general(request):
    start, end, days = _period(request)

    # -----------------------------
    # Filtres périmètre via session
    # -----------------------------
    region_id = request.session.get("region_id")
    departement_id = request.session.get("departement_id")

    region_name: Optional[str] = None
    departement_name: Optional[str] = None

    if region_id:
        try:
            region_name = Region.objects.only("Nom").get(pk=region_id).Nom
        except Region.DoesNotExist:
            region_name = None

    if departement_id:
        try:
            departement_name = Departement.objects.only("Nom").get(pk=departement_id).Nom
        except Departement.DoesNotExist:
            departement_name = None

    # ==================================================
    # SURVEILLANCE (KOBO)
    # ==================================================
    
    # ==================================================
    # VACCINATION (Objectif vs Réalisé)
    # ==================================================
    # ==================================================
    # LIMS (Demandes / Échantillons / Confirmées)
    # ==================================================
    demandes = Demande.objects.filter(cree_le__range=(start, end))
    if region_id:
        demandes = demandes.filter(region_id=region_id)
    if departement_id:
        demandes = demandes.filter(departement_id=departement_id)

    nb_demandes = demandes.count()

    demandes_par_etat = (
        demandes.values("current_etat__label")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    ech_qs = Echantillon.objects.filter(demande__in=demandes)
    nb_echantillons = ech_qs.count()
    nb_non_conformes = ech_qs.filter(conformite="non_conforme").count()

    top_matrices = (
        ech_qs.values("matrice")
        .annotate(n=Count("id"))
        .order_by("-n")[:8]
    )

    conf_qs = demandes.filter(suspicion_statut="confirmee")
    lims_confirme_par_maladie = (
        conf_qs.values("maladie_suspectee__Maladie")
        .annotate(n=Count("id"))
        .order_by("-n")
    )
    lims_confirme_par_region = (
        conf_qs.values("region__Nom")
        .annotate(n=Count("id"))
        .order_by("-n")
    )

    # ==================================================
    # Contexte
    # ==================================================
    kpi = {
        "jours": days,
        "lims_demandes": nb_demandes,
        "lims_echantillons": nb_echantillons,
        "lims_non_conformes": nb_non_conformes,
    }

    context = {
        "kpi": kpi,
        "start": start,
        "end": end,
        "demandes_par_etat": demandes_par_etat,
        "top_matrices": top_matrices,
        "lims_confirme_par_maladie": lims_confirme_par_maladie,
        "lims_confirme_par_region": lims_confirme_par_region,
        "current_region": region_name,
        "current_departement": departement_name,
    }
   
   
    return render(request, "homedashboard/home.html", context)

#Gestion des groupes utilisateurs
@group_required('Administrateur Système')
def system_admin_view(request):
    context =dashboard_general(request)
    if isinstance(context, HttpResponse):
     return context

@group_required('Administrateur Régional')
def regional_admin_view(request):
  context = dashboard_general(request)
  if isinstance(context, HttpResponse):
     return context

@group_required('Administrateur Départemental')
def departemental_admin_view(request):
   context = dashboard_general(request)
   if isinstance(context, HttpResponse):
     return context

@group_required('Animateur de la Surveillance')
def animateur_admin_view(request):
    context = dashboard_general(request)
    if isinstance(context, HttpResponse):
     return context

@group_required('Directeur de la Santé Animale')
def dsa_admin_view(request):
    context = dashboard_general(request)
    return render(request, 'profil/dsa_admin.html',context)

@group_required('Directeur Générale des services vétérinaires')
def dsa_admin_view(request):
    context = dashboard_general(request)
    return render(request, 'profil/dsa_admin.html',context)





@group_required('Gestionnaire des Médicaments')
def medicament_admin_view(request):
   
    context = dashboard_produit(request)
    if isinstance(context, HttpResponse):
     return context
    

@group_required("Services vétérinaires à l'aéroport")
def aibd_admin_view(request):
   
    context = dashboard_aibd(request)
    if isinstance(context, HttpResponse):
     return context
@group_required("Santé publique")  
def santePublique_admin_view(request):
   
    context = dashboard_sante_publique(request)
    if isinstance(context, HttpResponse):
     return context
    

    

@group_required('Superviseur de Campagne')
def superviseur_admin_view(request):
    context = tableau_de_bord(request)
    if isinstance(context, HttpResponse):
     return context
   
@group_required('Utilisateur Public')
def public_admin_view(request):
    return render(request, 'profil/public_admin.html')

@group_required('RH admin')
def rh_admin_view(request):
    
    return render(request, 'profil/rh_admin.html')


@group_required('Agent de suivi de demande')
def agent_suivi_admin_view(request):
    context = liste_demandes(request)
    if isinstance(context, HttpResponse):
     return context
    

###################utilisateurs labo

@group_required("Réceptioniste")  
def receptioniste_admin_view(request):
   
    context = demandes_list(request)
    if isinstance(context, HttpResponse):
     return context
@group_required("Analyste")  
def analyste_admin_view(request):
   
    context = demandes_list_affectees(request)
    if isinstance(context, HttpResponse):
     return context

@group_required("Directeur de laboratoire")  
def directeurlbao_admin_view(request):
   
    context = dashboard(request)
    if isinstance(context, HttpResponse):
     return context
    


#redirection des utilisateurs
def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
       # Region.objects.filter(Nom='Ouaddaï').delete()
        user = authenticate(request, username=username, password=password)
        if user is not None:
            auth_login(request, user)
            # Redirection basée sur le groupe de l'utilisateur
            if user.groups.filter(name='Administrateur Système').exists():
                return redirect('system_admin')
            elif user.groups.filter(name='Administrateur Régional').exists():
                return redirect('regional_admin')
            elif user.groups.filter(name='Administrateur Départemental').exists():
                return redirect('departemental_admin')
            elif user.groups.filter(name='Animateur de la Surveillance').exists():
                return redirect('animateur_admin')
            elif user.groups.filter(name='Directeur de la Santé Animale').exists():
                return redirect('dsa_admin')
            
            elif user.groups.filter(name='Directeur Générale des services vétérinaires').exists():
                return redirect('dsa_admin')
            elif user.groups.filter(name='Gestionnaire des Médicaments').exists():
                return redirect('medicament_admin')
            
            elif user.groups.filter(name= "Services vétérinaires à l'aéroport").exists():
                return redirect('aibd_admin')
            
            elif user.groups.filter(name= "Santé publique").exists():
                return redirect('santePublique_admin')
            
            elif user.groups.filter(name='Superviseur de Campagne').exists():
                return redirect('superviseur_admin')
            elif user.groups.filter(name='RH admin').exists():
                return redirect('rh_admin')
            elif user.groups.filter(name='Agent de suivi de demande').exists():
                return redirect('agent_suivi_admin')
            
            #############utilisateur labo
            elif user.groups.filter(name='Réceptioniste').exists():
                return redirect('receptioniste_admin')
            elif user.groups.filter(name='Analyste').exists():
                return redirect('analyste_admin')
            
            elif user.groups.filter(name='Directeur de laboratoire').exists():
                return redirect('directeurlbao_admin')
            
            
            else:
                return redirect('login')  # Redirection par défaut
        else:
            return render(request, 'index.html', {'error': 'Identifiants invalides'})
    return render(request,'index.html')




def logout_view(request):
    logout(request)
    return redirect('/')

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("login")
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})



# Vérifie si l'utilisateur fait partie du groupe "Administrateur Système"
def user_is_admin_system(user):
    return user.groups.filter(name='Administrateur Système').exists()





