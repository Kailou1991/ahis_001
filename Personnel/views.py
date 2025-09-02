from django.shortcuts import render, get_object_or_404, redirect
from .models import Personnel,Departement,Commune,Region
from Année.models import Année
from django.http import JsonResponse
from .forms import PersonnelForm
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from data_initialization.decorators import group_required
import matplotlib.pyplot as plt
import pandas as pd
import folium
from folium.plugins import HeatMap
import matplotlib.pyplot as plt
import pandas as pd
from django.db.models import Sum, F
from io import BytesIO
import base64
import matplotlib.pyplot as plt
import pandas as pd
import folium
import io
import urllib
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .models import Region, Departement, Commune
from .forms import RegionForm, DepartementForm, CommuneForm, TitreForm,EntiteForm


# Create View

@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Directeur de la Santé Animale')
def personnel_list(request):
    
    if request.user.groups.filter(name='Administrateur Système').exists() or request.user.groups.filter(name='Directeur de la Santé Animale').exists():
        personnel = Personnel.objects.all()
    elif request.user.groups.filter(name='Administrateur Régional').exists():
        region_id = request.session.get('region_id')
        if region_id is None:
            return HttpResponseForbidden("La région de l'utilisateur n'est pas définie.")
        personnel = Personnel.objects.filter(region_id=region_id)
    elif request.user.groups.filter(name='Administrateur Départemental').exists():
        departement_id = request.session.get('departement_id')
        if departement_id is None:
            return HttpResponseForbidden("Le département de l'utilisateur n'est pas défini.")
        personnel = Personnel.objects.filter(departement_id=departement_id)
    else:
        return HttpResponseForbidden("Vous n'avez pas la permission d'accéder à cette page.")
    
    return render(request, 'personnel/personnel_list.html', {'personnel': personnel})

# Détail d'un membre du personnel
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Directeur de la Santé Animale')
def personnel_detail(request, pk):
    personnel = get_object_or_404(Personnel, pk=pk)
    return render(request, 'personnel/personnel_detail.html', {'personnel': personnel})

# Créer un nouveau membre du personnel
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Directeur de la Santé Animale')
def personnel_create(request):
    if request.method == 'POST':
        form = PersonnelForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('personnel_list')
    else:
        form = PersonnelForm(user=request.user, session=request.session)
        regionForm=RegionForm()
        departementForm=DepartementForm()
        communeForm=CommuneForm()
        titreForm=TitreForm()
        entiteForm=EntiteForm()
        
    return render(request, 'personnel/personnel_form.html', {'entiteForm':entiteForm,'titreForm':titreForm,'communeForm':communeForm,'departementForm': departementForm,'form':form,'regionForm':regionForm})

@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Directeur de la Santé Animale')
def personnel_update(request, pk):
    personnel = get_object_or_404(Personnel, pk=pk)
    if request.method == 'POST':
        form = PersonnelForm(request.POST, instance=personnel,user=request.user, session=request.session)
        if form.is_valid():
            form.save()
            return redirect('personnel_list')
    else:
        form = PersonnelForm(instance=personnel,user=request.user, session=request.session)
        regionForm=RegionForm()
        departementForm=DepartementForm()
        communeForm=CommuneForm()
        titreForm=TitreForm()
        entiteForm=EntiteForm()
        
    return render(request, 'personnel/personnel_form.html', {'entiteForm':entiteForm,'titreForm':titreForm,'communeForm':communeForm,'departementForm': departementForm,'form':form,'regionForm':regionForm})

@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Directeur de la Santé Animale')
def personnel_delete(request, pk):
    personnel = get_object_or_404(Personnel, pk=pk)
    if request.method == 'POST':
        personnel.delete()
        return redirect('personnel_list')
    return render(request, 'personnel/personnel_confirm_delete.html', {'personnel': personnel})

#filtrage dynamique
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Directeur de la Santé Animale')
def get_departements(request):
    region_id = request.session.get('region_id')
    departement_id = request.session.get('departement_id')
    if not region_id or (not region_id  and not departement_id ) :
        region_id = request.GET.get('region_id')
        departements = Departement.objects.filter(Region_id=region_id).values('id', 'Nom')
    elif region_id and not departement_id:
        departements = Departement.objects.filter(Region_id=region_id).values('id', 'Nom')
    elif region_id and departement_id:
        departements = Departement.objects.filter(Region_id=region_id,id=departement_id).values('id', 'Nom')
    return JsonResponse(list(departements), safe=False)
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Directeur de la Santé Animale')
def get_communes(request):
    departement_id = request.session.get('departement_id')
    if not departement_id:
      departement_id = request.GET.get('departement_id')
    communes = Commune.objects.filter(DepartementID_id=departement_id).values('id', 'Nom')
    return JsonResponse(list(communes), safe=False)


def create_evolution_chart(personnel_queryset, start_year):
    # Courbe temporelle : Évolution des effectifs sur les 5 dernières années
    evolution_effectifs = personnel_queryset.filter(annee__gte=start_year).values('annee').annotate(total=Sum('nbre'))
    
    years = [entry['annee'] for entry in evolution_effectifs]
    counts = [entry['total'] for entry in evolution_effectifs]

    plt.figure(figsize=(10, 6))
    plt.plot(years, counts, marker='o')
    plt.xlabel('Année')
    plt.title('Évolution des Effectifs sur les 5 Dernières Années')
    for i, count in enumerate(counts):
        plt.text(years[i], count, str(count), ha='center', va='bottom')
    plt.gca().axes.get_yaxis().set_visible(False)

    fig = plt.gcf()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    string = base64.b64encode(buf.read())
    line_chart_uri = urllib.parse.quote(string)
    
    return line_chart_uri

@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Directeur de la Santé Animale')
def dashboard_personnel(request):
    current_year = datetime.now().year
    start_year = current_year - 5
    selected_annee = request.POST.get('annee', '')
    selected_region = request.POST.get('region', '')
    if request.user.groups.filter(name='Administrateur Système').exists() or request.user.groups.filter(name='Directeur de la Santé Animale').exists():
        personnel_queryset = Personnel.objects.all()
        if selected_annee:
            personnel_queryset = personnel_queryset.filter(annee=selected_annee)
        if selected_region:
            personnel_queryset = personnel_queryset.filter(region_id=selected_region)
    elif request.user.groups.filter(name='Administrateur Régional').exists():
        region_id = request.session.get('region_id')
        if region_id is None:
            return HttpResponseForbidden("La région de l'utilisateur n'est pas définie.")
        personnel_queryset = Personnel.objects.filter(region_id=region_id)
        if selected_annee:
                personnel_queryset = personnel_queryset.filter(annee=selected_annee)
        if selected_region:
                personnel_queryset = personnel_queryset.filter(region_id=selected_region)
    elif request.user.groups.filter(name='Administrateur Départemental').exists():
        departement_id = request.session.get('departement_id')
        if departement_id is None:
            return HttpResponseForbidden("Le département de l'utilisateur n'est pas défini.")
        personnel_queryset = Personnel.objects.filter(departement_id=departement_id)
        if selected_annee:
                personnel_queryset = personnel_queryset.filter(annee=selected_annee)
        if selected_region:
                personnel_queryset = personnel_queryset.filter(region_id=selected_region)
    else:
        return HttpResponseForbidden("Vous n'avez pas la permission d'accéder à cette page.")
    
    
    # Statistiques générales
    total_employes = personnel_queryset.aggregate(total=Sum('nbre'))['total']
    repartition_statut = personnel_queryset.values('position').annotate(total=Sum('nbre'))
    repartition_titre = personnel_queryset.values('titre__nom').annotate(total=Sum('nbre'))
    effectif_structure = personnel_queryset.values('entite_administrative__nom').annotate(total=Sum('nbre'))
    #effectif_region_commune = personnel_queryset.values('region__Nom', 'commune__Nom').annotate(total=Sum('nbre'))

    # Graphique en barres : Effectif par région et structure
    effectif_region = personnel_queryset.values('region__Nom').annotate(total=Sum('nbre'))
    effectif_commune = personnel_queryset.values('commune__Nom').annotate(total=Sum('nbre'))
    effectif_departement = personnel_queryset.values('departement__Nom').annotate(total=Sum('nbre'))
    
    effectif_structure = personnel_queryset.values('entite_administrative__nom').annotate(total=Sum('nbre'))
    if request.session.get('region_id') and request.session.get('departement_id'):
        regions = [entry['commune__Nom'] for entry in effectif_commune]
        region_counts = [entry['total'] for entry in effectif_commune]
        structures = [entry['entite_administrative__nom'] for entry in effectif_structure]
        structure_counts = [entry['total'] for entry in effectif_structure]

    elif request.session.get('region_id') and not request.session.get('departement_id'):
        regions = [entry['departement__Nom'] for entry in effectif_departement]
        region_counts = [entry['total'] for entry in effectif_departement]
        structures = [entry['entite_administrative__nom'] for entry in effectif_structure]
        structure_counts = [entry['total'] for entry in effectif_structure]

    elif not request.session.get('region_id') and not request.session.get('departement_id'):
        regions = [entry['region__Nom'] for entry in effectif_region]
        region_counts = [entry['total'] for entry in effectif_region]
        structures = [entry['entite_administrative__nom'] for entry in effectif_structure]
        structure_counts = [entry['total'] for entry in effectif_structure]

    plt.figure(figsize=(10, 6))
    plt.bar(regions, region_counts, label='Régions')
    plt.bar(structures, structure_counts, label='Structures', alpha=0.7)
    plt.xlabel('Entité / Structure')
    plt.title('Effectif par entité et Structure')
    
    for i, count in enumerate(region_counts):
        plt.text(i, count, str(count), ha='center', va='bottom')
    
    for i, count in enumerate(structure_counts):
        plt.text(i + len(region_counts), count, str(count), ha='center', va='bottom')

    plt.gca().axes.get_yaxis().set_visible(False)
    
    fig = plt.gcf()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    string = base64.b64encode(buf.read())
    bar_chart_uri = urllib.parse.quote(string)

    # Diagramme circulaire : Répartition par statut et titre
    positions = [entry['position'] for entry in repartition_statut]
    position_counts = [entry['total'] for entry in repartition_statut]
    
    titres = [entry['titre__nom'] for entry in repartition_titre]
    titre_counts = [entry['total'] for entry in repartition_titre]

    plt.figure(figsize=(8, 8))
    plt.pie(position_counts, labels=positions, autopct='%1.1f%%', startangle=140)
    plt.title('Répartition par Statut')

    fig = plt.gcf()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    string = base64.b64encode(buf.read())
    pie_chart_statut_uri = urllib.parse.quote(string)

    plt.figure(figsize=(8, 8))
    plt.pie(titre_counts, labels=titres, autopct='%1.1f%%', startangle=140)
    plt.title('Répartition par Titre')

    fig = plt.gcf()
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    string = base64.b64encode(buf.read())
    pie_chart_titre_uri = urllib.parse.quote(string)
    # Tableau du nombre de personnel par région, position et titre
    
    if request.session.get('region_id') and request.session.get('departement_id'):
        tableau_personnel_data = personnel_queryset.values('commune__Nom', 'position', 'titre__nom','annee').annotate(total=Sum('nbre')).order_by('commune__Nom', 'position', 'titre__nom','annee')

    elif request.session.get('region_id') and not request.session.get('departement_id'):
        tableau_personnel_data = personnel_queryset.values('departement__Nom', 'position', 'titre__nom','annee').annotate(total=Sum('nbre')).order_by('departement__Nom', 'position', 'titre__nom','annee')
    elif not request.session.get('region_id') and not request.session.get('departement_id'):
        tableau_personnel_data = personnel_queryset.values('region__Nom', 'position', 'titre__nom','annee').annotate(total=Sum('nbre')).order_by('region__Nom', 'position', 'titre__nom','annee')
    


    # Filtres pour le formulaire
    annee_filtre = Personnel.objects.values_list('annee', flat=True).distinct()
    if not request.session.get('region_id'):
      region_filtre = Region.objects.all()
    else:
         region_filtre = Region.objects.filter(id=request.session.get('region_id'))

    return render(request, 'personnel/dashboard_personnel.html', {
        'total_employes': total_employes,
        'bar_chart_data': bar_chart_uri,
        'pie_chart_statut_data': pie_chart_statut_uri,
        'pie_chart_titre_data': pie_chart_titre_uri,
        'tableau_personnel_data': tableau_personnel_data,
        'anneeFiltre': annee_filtre,
        'region_filtre': region_filtre,
        'selected_annee': selected_annee,
        'selected_region': selected_region
    })

###Modal#####################################################


@csrf_exempt
def add_region(request):
    if request.method == 'POST':
        form = RegionForm(request.POST)
        if form.is_valid():
            region = form.save()
            return JsonResponse({'id': region.id, 'Nom': region.Nom})
        else:
            return JsonResponse({'error': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def add_departement(request):
    if request.method == 'POST':
        form = DepartementForm(request.POST)
        if form.is_valid():
            departement = form.save()
            return JsonResponse({'id': departement.id, 'Nom': departement.Nom})
        else:
            return JsonResponse({'error': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def add_commune(request):
    if request.method == 'POST':
        form = CommuneForm(request.POST)
        if form.is_valid():
            commune = form.save()
            return JsonResponse({'id': commune.id, 'Nom': commune.Nom})
        else:
            return JsonResponse({'error': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def add_titre(request):
    if request.method == 'POST':
        form = TitreForm(request.POST)
        if form.is_valid():
            titre = form.save()
            return JsonResponse({'id': titre.id, 'nom': titre.nom})
        else:
            return JsonResponse({'error': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

import json
@csrf_exempt
def add_entite(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)  # Lire les données JSON
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)

        form = EntiteForm(data)  # Utiliser les données JSON
        if form.is_valid():
            entite = form.save()
            return JsonResponse({'id': entite.id, 'nom': entite.nom})
        else:
            return JsonResponse({'error': form.errors}, status=400)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)