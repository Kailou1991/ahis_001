from django.shortcuts import render, redirect, get_object_or_404
from .models import Infrastructure, Inspection
from .forms import InfrastructureForm, InspectionForm
import folium
from folium.plugins import MarkerCluster
from django.db.models import Count
from django.http import JsonResponse
from .models import Infrastructure, HistoriqueEtatInfrastructure
from .models import EtatInfrastructure, HistoriqueEtatInfrastructure
from django.shortcuts import render
from django.db.models import Count, Q, F
from datetime import datetime, timedelta
from Infrastructure.models import Infrastructure, Inspection, EtatInfrastructure, HistoriqueEtatInfrastructure, TypeInfrastructure, TypeFinancement
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune
from django.utils.timezone import now
from django.db.models.functions import TruncMonth
from django.contrib.auth.decorators import login_required
from django.db.models.functions import ExtractYear




# 🔹 Créer une infrastructure
@login_required
def infrastructure_create(request):

    from datetime import date

    form = InfrastructureForm(request.POST or None, request.FILES or None)
    if form.is_valid():
        infrastructure = form.save()

        # Créer une première inspection avec l'état initial
        Inspection.objects.create(
            infrastructure=infrastructure,
            date_inspection=date.today(),
            etat_derniere_inspection=None,
            etat_inspection=infrastructure.etat_initial,
            inspecteur="Création automatique",
            commentaire="Première inspection créée automatiquement lors de l'enregistrement."
        )

        return redirect('infrastructure_list')
    return render(request, 'infrastructure/form.html', {'form': form})


# 🔹 Lister toutes les infrastructures
@login_required
def infrastructure_list(request):
    infrastructures = Infrastructure.objects.all()
    return render(request, 'infrastructure/list.html', {'infrastructures': infrastructures})

# 🔹 Mettre à jour une infrastructure
@login_required
def infrastructure_update(request, pk):
    infrastructure = get_object_or_404(Infrastructure, pk=pk)
    form = InfrastructureForm(request.POST or None, request.FILES or None, instance=infrastructure)
    if form.is_valid():
        form.save()
        return redirect('infrastructure_list')
    return render(request, 'infrastructure/form.html', {'form': form, 'update': True})

# 🔹 Supprimer une infrastructure
@login_required
def infrastructure_delete(request, pk):
    infrastructure = get_object_or_404(Infrastructure, pk=pk)
    if request.method == 'POST':
        infrastructure.delete()
        return redirect('infrastructure_list')
    return render(request, 'infrastructure/confirm_delete.html', {'object': infrastructure, 'type': 'Infrastructure'})

# 🔹 Détail d’une infrastructure
@login_required
def infrastructure_detail(request, pk):
    infrastructure = get_object_or_404(Infrastructure, pk=pk)
    inspections = infrastructure.inspections.all().order_by('-date_inspection')
    return render(request, 'infrastructure/detail.html', {
        'infrastructure': infrastructure,
        'inspections': inspections
    })

# 🔹 Créer une inspection pour une infrastructure
@login_required
def inspection_create(request):
    form = InspectionForm(request.POST or None)

    if form.is_valid():
        inspection = form.save(commit=False)

        # ➕ Remplir automatiquement etat_derniere_inspection
        infra = inspection.infrastructure
        historique = HistoriqueEtatInfrastructure.objects.filter(
            infrastructure=infra
        ).order_by('-date_modification').first()

        if historique and historique.etat_inspection:
            inspection.etat_derniere_inspection = historique.etat_inspection
        else:
            try:
                inspection.etat_derniere_inspection = EtatInfrastructure.objects.get(libelle=infra.get_etat_initial_display())
            except EtatInfrastructure.DoesNotExist:
                inspection.etat_derniere_inspection = None

        inspection.save()  # le signal se charge de créer l'historique

        return redirect('inspection_list')  # ou autre vue
    return render(request, 'infrastructure/inspection_form.html', {'form': form})


# 🔹 Lister toutes les inspections
@login_required
def inspection_list(request):
    inspections = Inspection.objects.select_related('infrastructure', 'etat_inspection')
    return render(request, 'infrastructure/inspection_list.html', {'inspections': inspections})

# 🔹 Mettre à jour une inspection
@login_required
def inspection_update(request, pk):
    inspection = get_object_or_404(Inspection, pk=pk)
    form = InspectionForm(request.POST or None, instance=inspection)
    if form.is_valid():
        form.save()
        return redirect('inspection_list')
    return render(request, 'infrastructure/inspection_form.html', {'form': form, 'update': True})

# 🔹 Supprimer une inspection
@login_required
def inspection_delete(request, pk):
    inspection = get_object_or_404(Inspection, pk=pk)
    infrastructure_id = inspection.infrastructure.pk  # utilisé pour la redirection après suppression

    if request.method == 'POST':
        inspection.delete()
        return redirect('inspection_list', infrastructure_id)

    return render(request, 'infrastructure/inspection_confirm_delete.html', {
        'object': inspection
    })


# 🔹 Détail d’une inspection
@login_required
def inspection_detail(request, pk):
    inspection = get_object_or_404(Inspection, pk=pk)
    return render(request, 'infrastructure/inspection_detail.html', {
        'inspection': inspection
    })


# 🔹 Tableau de bord analytique
@login_required
def dashboard_infrastructure_view(request):
    total_par_etat = Infrastructure.objects.values('etat_initial').annotate(total=Count('id'))
    total_inspections = Inspection.objects.count()
    total_fonctionnels = Inspection.objects.filter(etat_inspection__libelle='Fonctionnel').count()

    return render(request, 'infrastructure/dashboard.html', {
        'total_par_etat': total_par_etat,
        'total_inspections': total_inspections,
        'total_fonctionnels': total_fonctionnels,
    })



def get_etat_precedent(request):
    infrastructure_id = request.GET.get('infrastructure_id')
    if infrastructure_id:
        try:
            infra = Infrastructure.objects.get(pk=infrastructure_id)
            historique = HistoriqueEtatInfrastructure.objects.filter(infrastructure=infra).order_by('-date_modification').first()
            if historique and historique.etat_inspection:
                return JsonResponse({
                    'etat': historique.etat_inspection.libelle,
                    'etat_id': historique.etat_inspection.id
                })
            else:
                return JsonResponse({
                    'etat': infra.get_etat_initial_display(),
                    'etat_id': None
                })
        except Infrastructure.DoesNotExist:
            return JsonResponse({'etat': '', 'etat_id': ''})
    return JsonResponse({'etat': '', 'etat_id': ''})


# dashboard/views.pys
@login_required
def dashboard_infrastructure_view(request):
    
    from django.db.models.functions import TruncMonth, ExtractYear
    

    today = datetime.today()
    year_ago = today - timedelta(days=365)

    # Filtres
    region_id = request.GET.get('region')
    departement_id = request.GET.get('departement')
    commune_id = request.GET.get('commune')
    annee = request.GET.get('annee')

    infrastructures = Infrastructure.objects.all()
    if region_id:
        infrastructures = infrastructures.filter(region_id=region_id)
    if departement_id:
        infrastructures = infrastructures.filter(departement_id=departement_id)
    if commune_id:
        infrastructures = infrastructures.filter(commune_id=commune_id)

    inspections = Inspection.objects.filter(infrastructure__in=infrastructures)
    if annee:
        inspections = inspections.filter(date_inspection__year=annee)

    total_infra = infrastructures.count()

    # Dernier état réel (Historique ou état initial)
    historiques = (HistoriqueEtatInfrastructure.objects
        .filter(infrastructure__in=infrastructures)
        .order_by('infrastructure_id', '-date_modification'))

    latest_state_map = {}
    for hist in historiques:
        if hist.infrastructure_id not in latest_state_map:
            latest_state_map[hist.infrastructure_id] = hist.etat_inspection.libelle

    etats = EtatInfrastructure.objects.values_list('libelle', flat=True)
    infra_etats = {etat: 0 for etat in etats}

    for infra in infrastructures:
        etat = latest_state_map.get(infra.id, infra.etat_initial)
        if etat in infra_etats:
            infra_etats[etat] += 1

    # Taux de couverture
    infra_with_inspections = inspections.values('infrastructure').distinct().count()
    coverage_pct = (infra_with_inspections / total_infra * 100) if total_infra else 0

    # Infrastructures sans GPS
    infra_no_gps = infrastructures.filter(Q(latitude__isnull=True) | Q(longitude__isnull=True)).count()

    # Inspections périmées > 12 mois
    old_inspections = 0
    for infra in infrastructures:
        last = infra.inspections.order_by('-date_inspection').first()
        if not last or last.date_inspection < year_ago.date():
            old_inspections += 1

    # Graphique par mois
    inspections_by_month = (inspections
        .annotate(month=TruncMonth('date_inspection'))
        .values('month')
        .annotate(total=Count('id'))
        .order_by('month'))

    # Répartition type/financement
    repartition_type = infrastructures.values(name=F('type_infrastructure__nom')).annotate(total=Count('id'))
    repartition_financement = infrastructures.values(name=F('type_financement__nom')).annotate(total=Count('id'))

    # Maillage territorial
    maillage_commune = (infrastructures
        .values(
            Region=F('region__Nom'),
            Departement=F('departement__Nom'),
            Commune=F('commune__Nom'),
            type=F('type_infrastructure__nom')
        )
        .annotate(total=Count('id'))
        .order_by('Region', 'Departement', 'Commune', 'type'))

    annees = Inspection.objects.annotate(year=ExtractYear('date_inspection')).values_list('year', flat=True).distinct().order_by('year')

    context = {
        'total_infra': total_infra,
        'infra_etats': infra_etats,
        'total_inspections': inspections.count(),
        'coverage_pct': round(coverage_pct, 2),
        'infra_no_gps': infra_no_gps,
        'old_inspections': old_inspections,
        'inspections_by_month': inspections_by_month,
        'repartition_type': repartition_type,
        'repartition_financement': repartition_financement,
        'regions': Region.objects.all(),
        'departements': Departement.objects.all(),
        'communes': Commune.objects.all(),
        'selected_region': int(region_id) if region_id else None,
        'selected_departement': int(departement_id) if departement_id else None,
        'selected_commune': int(commune_id) if commune_id else None,
        'selected_annee': int(annee) if annee else None,
        'annees': annees,
        'maillage_commune': maillage_commune,
    }

    return render(request, 'infrastructure/dashboard.html', context)


# 🔹 Carte interactive des infrastructures
@login_required
def carte_infrastructure_folium(request):
    etat_filter = request.GET.get('etat')
    annee_filter = request.GET.get('annee')

    infrastructures = Infrastructure.objects.filter(latitude__isnull=False, longitude__isnull=False)

    if annee_filter:
        inspected_ids = Inspection.objects.filter(
            date_inspection__year=annee_filter
        ).values_list('infrastructure_id', flat=True)
        infrastructures = infrastructures.filter(id__in=inspected_ids)

    if etat_filter:
        hist_ids = HistoriqueEtatInfrastructure.objects.filter(
            etat_inspection__libelle=etat_filter
        ).values_list('infrastructure_id', flat=True)
        infrastructures = infrastructures.filter(id__in=hist_ids)

    # Calcul du centre géographique
    latitudes = [infra.latitude for infra in infrastructures]
    longitudes = [infra.longitude for infra in infrastructures]
    if latitudes and longitudes:
        center_lat = sum(latitudes) / len(latitudes)
        center_lon = sum(longitudes) / len(longitudes)
    else:
        # Coordonnées par défaut si aucune infrastructure n'est disponible
        center_lat = 17.570692  # Exemple : centre du Mali
        center_lon = -3.996166

    # Création de la carte centrée dynamiquement
    folium_map = folium.Map(location=[center_lat, center_lon], zoom_start=6, control_scale=True)
    marker_cluster = MarkerCluster().add_to(folium_map)

    # Ajout des marqueurs
    type_infras = TypeInfrastructure.objects.filter(infrastructure__in=infrastructures).distinct()
    color_palette = ['red', 'green', 'blue', 'orange', 'purple', 'darkred', 'cadetblue', 'darkblue', 'gray', 'black']
    color_map = {t.id: color_palette[i % len(color_palette)] for i, t in enumerate(type_infras)}

    for infra in infrastructures:
        popup = f"<strong>{infra.nom}</strong><br>{infra.type_infrastructure.nom}<br>{infra.commune.Nom if infra.commune else ''}"
        folium.Marker(
            location=[infra.latitude, infra.longitude],
            popup=popup,
            icon=folium.Icon(color=color_map.get(infra.type_infrastructure.id, 'gray'), icon="info-sign")
        ).add_to(marker_cluster)

    # Création de la légende HTML
    legend_html = '''
     <div style="
     position: absolute; 
     top: 100px; left: 20px; width: 200px; 
     background-color: white; 
     border:2px solid grey; 
     z-index:9999; 
     font-size:14px;
     padding: 10px;
     ">
     <b>Légende</b><br>
    '''
    for t in type_infras:
        color = color_map.get(t.id, 'gray')
        legend_html += f'<i class="fa fa-map-marker fa-2x" style="color:{color}"></i> {t.nom}<br>'
    legend_html += '</div>'

    folium_map.get_root().html.add_child(folium.Element(legend_html))

    map_html = folium_map._repr_html_()

    annees = [d.year for d in Inspection.objects.dates('date_inspection', 'year')]

    context = {
        'map_html': map_html,
        'etats': EtatInfrastructure.objects.all(),
        'types_utilisés': type_infras,
        'color_map': color_map,
        'annees': annees,
        'selected_etat': etat_filter,
        'selected_annee': int(annee_filter) if annee_filter else None
    }
    return render(request, 'infrastructure/webmap.html', context)



# 🔹 Exportations des données
@login_required
def export_infrastructures_csv(request):
    import csv
    from django.http import HttpResponse
    etat_filter = request.GET.get('etat')
    annee_filter = request.GET.get('annee')

    infrastructures = Infrastructure.objects.filter(latitude__isnull=False, longitude__isnull=False)

    if annee_filter:
        try:
            annee = int(annee_filter)
            inspected_ids = Inspection.objects.filter(
                date_inspection__year=annee
            ).values_list('infrastructure_id', flat=True)
            infrastructures = infrastructures.filter(id__in=inspected_ids)
        except (ValueError, TypeError):
            pass  # Ignore le filtre si l'année n'est pas valide

    if etat_filter:
        hist_ids = HistoriqueEtatInfrastructure.objects.filter(
            etat_inspection__libelle=etat_filter
        ).values_list('infrastructure_id', flat=True)
        infrastructures = infrastructures.filter(id__in=hist_ids)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="infrastructures.csv"'

    writer = csv.writer(response)
    writer.writerow(['Nom', 'Type', 'État initial', 'Latitude', 'Longitude', 'Commune'])

    for infra in infrastructures:
        writer.writerow([
            infra.nom,
            infra.type_infrastructure.nom,
            infra.etat_initial.libelle if infra.etat_initial else '',
            infra.latitude,
            infra.longitude,
            infra.commune.Nom if infra.commune else ''
        ])

    return response