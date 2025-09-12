from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from data_initialization.decorators import group_required
from django.db.models import Count, Sum, Avg
from django.db.models.functions import TruncMonth
from django.http import HttpResponse
from .models import DeplacementAnimal, Espece
from .form import DeplacementAnimauxForm
from datetime import date
import matplotlib.pyplot as plt
import numpy as np
import base64
import io
import pandas as pd
from django.utils.timezone import now


# ✅ VUES CRUD

@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires', 'Administrateur Régional', 'Administrateur Départemental', 'Directeur de la Santé Animale')
def deplacementanimaux_list(request):
    deplacements = DeplacementAnimal.objects.all()
    return render(request, 'DeplacementAnimaux/deplacementanimaux_list.html', {'deplacements': deplacements})

@login_required
@group_required('Administrateur Système', 'Directeur Générale des services vétérinaires','Administrateur Régional', 'Administrateur Départemental', 'Directeur de la Santé Animale')
def deplacementanimaux_detail(request, pk):
    deplacement = get_object_or_404(DeplacementAnimal, pk=pk)
    return render(request, 'DeplacementAnimaux/deplacementanimaux_detail.html', {'deplacement': deplacement})




@login_required
@group_required('Administrateur Système', 'Administrateur Régional', 'Administrateur Départemental', 'Directeur de la Santé Animale')
def deplacementanimaux_create(request):
    form = DeplacementAnimauxForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect('deplacementanimaux_list')
    else:
     return render(request, 'DeplacementAnimaux/deplacementanimaux_form.html', {'form': form})

@login_required
@group_required('Administrateur Système', 'Administrateur Régional', 'Administrateur Départemental', 'Directeur de la Santé Animale')
def deplacementanimaux_update(request, pk):
    deplacement = get_object_or_404(DeplacementAnimal, pk=pk)
    form = DeplacementAnimauxForm(request.POST or None, request.FILES or None, instance=deplacement)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Déplacement mis à jour avec succès.")
        return redirect('deplacementanimaux_detail', pk=pk)
    return render(request, 'DeplacementAnimaux/deplacementanimaux_form.html', {'form': form})

@login_required
@group_required('Administrateur Système', 'Administrateur Régional', 'Administrateur Départemental', 'Directeur de la Santé Animale')
def deplacementanimaux_delete(request, pk):
    deplacement = get_object_or_404(DeplacementAnimal, pk=pk)
    if request.method == "POST":
        deplacement.delete()
        messages.success(request, "Déplacement supprimé avec succès.")
        return redirect('deplacementanimaux_list')
    return render(request, 'DeplacementAnimaux/deplacementanimaux_confirm_delete.html', {'deplacement': deplacement})

# dashboard

from django.shortcuts import render
from django.db.models import Count, Sum, Avg
from django.db.models.functions import TruncMonth
from django.contrib.auth.decorators import login_required
from .models import DeplacementAnimal
from Espece.models import Espece
from Region.models import Region
import folium
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import io, base64
from folium.plugins import MarkerCluster
from django.core.serializers import serialize
import json


def convert_plot_to_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    return image_base64


def generate_movement_histogram(queryset):
    monthly = queryset.annotate(month=TruncMonth('date_deplacement')) \
        .values('month') \
        .annotate(count=Count('id')) \
        .order_by('month')
    x = [d['month'].strftime("%b %Y") for d in monthly]
    y = [d['count'] for d in monthly]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(x, y, color='skyblue')
    ax.set_title("Déplacements par Mois")
    ax.set_ylabel("Nombre")
    return convert_plot_to_base64(fig)

def generate_sanitary_bar_chart(queryset):
    from matplotlib.ticker import NullLocator

    # Grouper par maladie suspectée
    grouped = queryset.filter(maladie_suspectee__isnull=False) \
        .values('maladie_suspectee__Maladie') \
        .annotate(
            malades=Sum('nombre_animaux_malades'),
            traites=Sum('nombre_animaux_traites'),
            quarantaine=Sum('nombre_animaux_quarantaine'),
        ).order_by('-malades')

    maladies = [entry['maladie_suspectee__Maladie'] for entry in grouped]
    malades = [entry['malades'] or 0 for entry in grouped]
    traites = [entry['traites'] or 0 for entry in grouped]
    quarantaine = [entry['quarantaine'] or 0 for entry in grouped]

    x = np.arange(len(maladies))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))
    bars1 = ax.bar(x - width, malades, width, label='Malades')
    bars2 = ax.bar(x, traites, width, label='Traités')
    bars3 = ax.bar(x + width, quarantaine, width, label='Quarantaine')

    # Axe X = noms des maladies
    ax.set_xticks(x)
    ax.set_xticklabels(maladies, rotation=45, ha='right')

    # Suppression axe Y
    ax.set_yticks([])
    ax.yaxis.set_major_locator(NullLocator())

    # Titre
    ax.set_title("Surveillance sanitaire par maladie suspectée")

    # Légende en haut
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, 1.15), ncol=3)

    # Étiquettes au-dessus des barres
    for bars in [bars1, bars2, bars3]:
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.text(bar.get_x() + bar.get_width() / 2, height + 0.5,
                        f'{int(height)}', ha='center', va='bottom', fontsize=8)

    return convert_plot_to_base64(fig)


def generate_transport_pie_chart(queryset):
    transport_data = (
        queryset.values('mode_transport')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    labels = [entry['mode_transport'] for entry in transport_data]
    counts = [entry['total'] for entry in transport_data]

    fig, ax = plt.subplots(figsize=(7, 7))
    wedges, texts, autotexts = ax.pie(
        counts,
        labels=labels,
        autopct='%1.1f%%',
        startangle=90,
        textprops={'fontsize': 9}
    )

    ax.axis('equal')  # Assure que le cercle est rond
    ax.set_title("Répartition des modes de transport")
    ax.legend(wedges, labels, title="Modes", loc="upper center", bbox_to_anchor=(0.5, 1.1), ncol=2)

    return convert_plot_to_base64(fig)


def generate_movement_map(queryset):
    base_map = folium.Map(location=[12, 1], zoom_start=6)
    cluster = MarkerCluster().add_to(base_map)

    for dep in queryset:
        if dep.latitude_poste_controle is not None and dep.longitude_poste_controle is not None:
            folium.Marker(
                location=[dep.latitude_poste_controle, dep.longitude_poste_controle],
                popup=(
                    f"<strong>Déplacement :</strong> {dep.espece} <br>"
                    f"<strong>Animaux :</strong> {dep.nombre_animaux}<br>"
                    f"<strong>Date :</strong> {dep.date_deplacement}<br>"
                    f"<strong>Provenance :</strong> {dep.commune_provenance} <br>"
                    f"<strong>Destination :</strong> {dep.commune_destination}"
                ),
                icon=folium.Icon(color='blue', icon='paw')
            ).add_to(cluster)

    return base_map._repr_html_()



@login_required
@group_required('Administrateur Système', 'Directeur Générale des services vétérinaires','Administrateur Régional', 'Administrateur Départemental', 'Directeur de la Santé Animale')
def tableau_de_bord(request):
    # Filtres
    espece_id = request.POST.get("espece")
    mode_transport = request.POST.get("mode_transport")
    date_start = request.POST.get("date_start")
    date_end = request.POST.get("date_end")

    deplacements = DeplacementAnimal.objects.all()
    if request.method == "POST":
        if espece_id:
            deplacements = deplacements.filter(espece_id=espece_id)
        if mode_transport:
            deplacements = deplacements.filter(mode_transport=mode_transport)
        if date_start and date_end:
            deplacements = deplacements.filter(date_deplacement__range=[date_start, date_end])

    # KPI classiques
    total_deplacements = deplacements.count()
    total_animaux = deplacements.aggregate(Sum('nombre_animaux'))['nombre_animaux__sum'] or 0
    moyenne_animaux = deplacements.aggregate(Avg('nombre_animaux'))['nombre_animaux__avg'] or 0
    cas_suspects = deplacements.filter(maladie_detectee="OUI").count()
    total_malades = deplacements.aggregate(Sum('nombre_animaux_malades'))['nombre_animaux_malades__sum'] or 0
    total_quarantaine = deplacements.aggregate(Sum('nombre_animaux_quarantaine'))['nombre_animaux_quarantaine__sum'] or 0

    # Nouveaux KPI
    nb_certif_ctrl = deplacements.aggregate(Sum('nombre_certificats_vaccination_controles'))['nombre_certificats_vaccination_controles__sum'] or 0
    nb_certif_delivre = deplacements.aggregate(Sum('nombre_certificats_vaccination_delivres'))['nombre_certificats_vaccination_delivres__sum'] or 0
    nb_pass_ctrl = deplacements.aggregate(Sum('nombre_laisser_passer_controles'))['nombre_laisser_passer_controles__sum'] or 0
    nb_pass_delivre = deplacements.aggregate(Sum('nombre_laisser_passer_delivres'))['nombre_laisser_passer_delivres__sum'] or 0

    kpis = [
        ("Total mouvements", total_deplacements, "info", "fa-truck"),
        ("Total animaux déplacés", total_animaux, "primary", "fa-paw"),
        ("Moyenne depla/dep.", moyenne_animaux, "success", "fa-balance-scale"),
        ("Malades", total_malades, "warning", "fa-stethoscope"),
        ("Quarantaine", total_quarantaine, "secondary", "fa-procedures"),
        ("Certificats vaccin.contrôlés", nb_certif_ctrl, "dark", "fa-clipboard-check"),
        ("Certificats vaccin.délivrés", nb_certif_delivre, "info", "fa-certificate"),
        (" Laisser-passer contrôlés", nb_pass_ctrl, "warning", "fa-id-card"),
        ("Laisser-passer délivrés", nb_pass_delivre, "primary", "fa-file-signature"),
    ]

    # Graphiques
    histogram_chart = generate_movement_histogram(deplacements)
    sanitary_chart = generate_sanitary_bar_chart(deplacements)
    transport_chart = generate_transport_pie_chart(deplacements)

    # Carte
    movement_map = generate_movement_map(deplacements)

    # Analyse régionale
    top_depart = deplacements.values('region_provenance__Nom').annotate(total=Count('id')).order_by('-total')[:5]
    top_arrivee = deplacements.values('region_destination__Nom').annotate(total=Count('id')).order_by('-total')[:5]

    # Derniers enregistrements
    derniers = deplacements.order_by('-date_deplacement')[:10]

    return render(request, 'DeplacementAnimaux/tableau_de_bord.html', {
        'especes': Espece.objects.all(),
        'mode_transport_choices': DeplacementAnimal.ModeTransport.choices,
        'kpis': kpis,
        'histogram_chart': histogram_chart,
        'sanitary_chart': sanitary_chart,
        'transport_chart': transport_chart,
        'movement_map': movement_map,
        'top_depart': top_depart,
        'top_arrivee': top_arrivee,
        'derniers_deplacements': derniers,
        'request': request,
    })

# ✅ EXPORT EXCEL

@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires', 'Administrateur Régional', 'Administrateur Départemental', 'Directeur de la Santé Animale')
def export_deplacement_animaux_xls(request):
    deplacements = DeplacementAnimal.objects.all()
    data = []

    for dep in deplacements:
        data.append({
            'ID': dep.id,
            'Espèce': dep.espece.Espece if dep.espece else "",
            'Nombre d\'animaux': dep.nombre_animaux,
            'Région provenance': dep.region_provenance.Nom if dep.region_provenance else "",
            'Département provenance': dep.departement_provenance.Nom if dep.departement_provenance else "",
            'Commune provenance': dep.commune_provenance.Nom if dep.commune_provenance else "",
            'Région destination': dep.region_destination.Nom if dep.region_destination else "",
            'Département destination': dep.departement_destination.Nom if dep.departement_destination else "",
            'Commune destination': dep.commune_destination.Nom if dep.commune_destination else "",
            'Établissement origine': dep.etablissement_origine or "",
            'Établissement destination': dep.etablissement_destination or "",
            'Date déplacement': dep.date_deplacement,
            'Durée (jours)': dep.duree_deplacement or "",
            'Mode de transport': dep.get_mode_transport_display(),
            'Raison déplacement': dep.raison_deplacement or "",
            'Nom propriétaire': dep.nom_proprietaire or "",
            'Contact propriétaire': dep.contact_proprietaire or "",
            'Nom transporteur': dep.nom_transporteur or "",
            'Contact transporteur': dep.contact_transporteur or "",
            'Latitude poste de contrôle': dep.latitude_poste_controle or "",
            'Longitude poste de contrôle': dep.longitude_poste_controle or "",
            'Maladie détectée': dep.maladie_detectee,
            'Maladie suspectée': dep.maladie_suspectee.Maladie if dep.maladie_suspectee else "",
            'Animaux malades': dep.nombre_animaux_malades or 0,
            'Animaux traités': dep.nombre_animaux_traites or 0,
            'Animaux vaccinés': dep.nombre_animaux_vaccines or 0,
            'Animaux en quarantaine': dep.nombre_animaux_quarantaine or 0,
            'Mesures sanitaires': dep.mesures_prises or "",
        })

    df = pd.DataFrame(data)

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="deplacement_animaux.xlsx"'

    with pd.ExcelWriter(response, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Déplacements')

    return response




def get_departements(request):
    from django.http import JsonResponse
    from Departement.models import Departement
    from Commune.models import Commune
    region_id = request.GET.get("region_id")
    departements = Departement.objects.filter(Region=region_id).values("id", "Nom")
    return JsonResponse(list(departements), safe=False)

def get_communes(request):
    from django.http import JsonResponse
    from Departement.models import Departement
    from Commune.models import Commune
    departement_id = request.GET.get("departement_id")
    communes = Commune.objects.filter(DepartementID=departement_id).values("id", "Nom")
    return JsonResponse(list(communes), safe=False)
