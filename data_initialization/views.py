
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
from Foyer.models import Foyer
from Infrastructure.models import Infrastructure

###utilsation des vues pour le dashbord global
from DeplacementAnimaux.views import*
from Infrastructure.views import*
from Foyer.views import *
from Personnel.views import*
from produit.views import*
from actes_admin.views import liste_demandes
from Foyer.views import generer_carte_foyers
from aibd.views import dashboard_aibd
from sante_publique.views import dashboard_sante_publique
from lims.views_demandes import demandes_list
from lims.views_dashboard import dashboard
from lims.views import demandes_list_affectees
from generated_apps.surveillance_sn.views_dashboard import dashboard_surveillance


from datetime import timedelta
from typing import Optional, List, Dict

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum, F, IntegerField
from django.db.models.functions import Coalesce, Trim
from django.shortcuts import render
from django.utils import timezone

# === Adapte ces imports aux noms réels de tes apps ===
from generated_apps.surveillance_sn.models import (
    SurveillanceSn,
    SurveillanceSnChild783b28ae as SurvChild,
)
from generated_apps.vaccination_sn.models import (
    VaccinationSn,
    VaccinationSnChild0c8ff1d1 as VaccChild,
)
from generated_apps.objectif_sn.models import (
    ObjectifSn,
    ObjectifSnChild0c8ff1d1 as ObjChild,
)
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
    surv_qs = SurveillanceSn.objects.filter(submission_time__range=(start, end))
    if region_name:
        surv_qs = surv_qs.filter(grp3_region__iexact=region_name.strip())
    if departement_name:
        surv_qs = surv_qs.filter(grp3_departement__iexact=departement_name.strip())

    surv_count = surv_qs.count()
    alertes_actives = surv_qs.filter(status__icontains="aler").count()

    top_signes = (
        surv_qs.values("grp5_liste_signes")
        .annotate(n=Count("id"))
        .order_by("-n")[:10]
    )

    # AGG chiffrées (pas d'expressions dans le template)
    surv_child = SurvChild.objects.filter(parent__in=surv_qs)
    agg_surv = surv_child.aggregate(
        total_malade=Coalesce(Sum("total_malade"), 0, output_field=IntegerField()),
        fem_ad=Coalesce(Sum("nb_femelles_adultes_mortes"), 0, output_field=IntegerField()),
        fem_jeunes=Coalesce(Sum("nb_jeunes_femelles_mortes"), 0, output_field=IntegerField()),
        mal_jeunes=Coalesce(Sum("nb_jeunes_males_morts"), 0, output_field=IntegerField()),
        mal_ad=Coalesce(Sum("nb_males_adultes_morts"), 0, output_field=IntegerField()),
    )
    total_malades = int(agg_surv["total_malade"])
    total_morts = int(agg_surv["fem_ad"] + agg_surv["fem_jeunes"] + agg_surv["mal_jeunes"] + agg_surv["mal_ad"])

    # ==================================================
    # VACCINATION (Objectif vs Réalisé)
    # ==================================================
    # ⚠️ Filtrer sur (submission_time DANS période) OU (datesaisie DANS période) OU, à défaut, created_at
    vacc_parents = VaccinationSn.objects.filter(
        Q(submission_time__range=(start, end)) |
        Q(datesaisie__range=(start.date(), end.date())) |
        Q(created_at__range=(start, end))
    )
    if region_name:
        vacc_parents = vacc_parents.filter(grp4_region__iexact=region_name.strip())
    if departement_name:
        vacc_parents = vacc_parents.filter(grp4_departement__iexact=departement_name.strip())

    # Enfants liés aux parents retenus
    vacc_children = VaccChild.objects.filter(parent__in=vacc_parents)

    # Réalisés (NULL-safe) : public + privé ; fallback marques puis calculation
    agg_vacc = vacc_children.aggregate(
        v_pub=Coalesce(Sum("vaccine_public"), 0, output_field=IntegerField()),
        v_pri=Coalesce(Sum("vaccine_prive"), 0, output_field=IntegerField()),
        marques=Coalesce(Sum("total_marque"), 0, output_field=IntegerField()),
        calc=Coalesce(Sum("calculation"), 0, output_field=IntegerField()),
    )
    vacc_realise = int(agg_vacc["v_pub"]) + int(agg_vacc["v_pri"])
    if vacc_realise == 0:
        vacc_realise = int(agg_vacc["marques"]) or int(agg_vacc["calc"])

    # Objectifs / Éligibles (même logique de période : submission_time OU created_at)
    obj_parents = ObjectifSn.objects.filter(
        Q(submission_time__range=(start, end)) |
        Q(created_at__range=(start, end))
    )
    if region_name:
        obj_parents = obj_parents.filter(grp4_region__iexact=region_name.strip())
    if departement_name:
        obj_parents = obj_parents.filter(grp4_departement__iexact=departement_name.strip())

    obj_children = ObjChild.objects.filter(parent__in=obj_parents)

    vacc_objectif = int(obj_children.aggregate(total=Coalesce(Sum("effectif_cible"), 0, output_field=IntegerField()))["total"])
    vacc_eligible = int(obj_children.aggregate(total=Coalesce(Sum("effectif_elligible"), 0, output_field=IntegerField()))["total"])

    couverture_pct = round((vacc_realise / vacc_objectif) * 100, 1) if vacc_objectif else 0.0

    # Top maladies (mêmes enfants filtrés) avec fallback si public/privé à 0
    top_base = vacc_children.values("maladie_masse").annotate(
        v_pub=Coalesce(Sum("vaccine_public"), 0, output_field=IntegerField()),
        v_pri=Coalesce(Sum("vaccine_prive"), 0, output_field=IntegerField()),
        marques=Coalesce(Sum("total_marque"), 0, output_field=IntegerField()),
        calc=Coalesce(Sum("calculation"), 0, output_field=IntegerField()),
    )

    vacc_top_maladies: List[Dict] = []
    for r in top_base:
        total = int(r["v_pub"]) + int(r["v_pri"])
        if total == 0:
            total = int(r["marques"]) or int(r["calc"])
        vacc_top_maladies.append({"maladie_masse": r["maladie_masse"], "total": total})
    vacc_top_maladies.sort(key=lambda x: x["total"], reverse=True)
    vacc_top_maladies = vacc_top_maladies[:10]

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
        "surv_total": surv_count,
        "surv_alertes": alertes_actives,
        "surv_malades": total_malades,
        "surv_morts": total_morts,
        "vacc_objectif": vacc_objectif,
        "vacc_eligible": vacc_eligible,
        "vacc_realise": vacc_realise,
        "vacc_couverture": couverture_pct,
        "lims_demandes": nb_demandes,
        "lims_echantillons": nb_echantillons,
        "lims_non_conformes": nb_non_conformes,
    }

    context = {
        "kpi": kpi,
        "start": start,
        "end": end,
        "top_signes": top_signes,
        "vacc_top_maladies": vacc_top_maladies,
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





