# views.py
from django.shortcuts import render, get_object_or_404, redirect
from .models import *
from .forms import *
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.db.models import Sum, Count
from .models import (
    RegistreAbattage, RegistreInspectionAnteMortem, RegistreSaisiesTotales,
    RegistreSaisiesOrganes, InspectionViande
)
from .forms import PeriodeRapportForm
from datetime import datetime, timedelta

import openpyxl
from django.http import HttpResponse
from django.core.paginator import Paginator




# CRUD views pour RegistreAbattage

def liste_abattage(request):
    enregistrements = RegistreAbattage.objects.all()
    return render(request, 'sante_publique/abattage_liste.html', {'enregistrements': enregistrements})

def ajouter_abattage(request):
    form = RegistreAbattageForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('liste_abattage')
    return render(request, 'sante_publique/abattage_form.html', {'form': form})

def modifier_abattage(request, pk):
    obj = get_object_or_404(RegistreAbattage, pk=pk)
    form = RegistreAbattageForm(request.POST or None, instance=obj)
    if form.is_valid():
        form.save()
        return redirect('liste_abattage')
    return render(request, 'sante_publique/abattage_form.html', {'form': form})

def supprimer_abattage(request, pk):
    obj = get_object_or_404(RegistreAbattage, pk=pk)
    if request.method == 'POST':
        obj.delete()
        return redirect('liste_abattage')
    return render(request, 'sante_publique/abattage_confirm_delete.html', {'objet': obj})


@login_required
def liste_ante_mortem(request):
    enregistrements = RegistreInspectionAnteMortem.objects.all()
    return render(request, 'sante_publique/ante_mortem_liste.html', {'enregistrements': enregistrements})

@login_required
def ajouter_ante_mortem(request):
    form = RegistreInspectionAnteMortemForm(request.POST or None)
    if form.is_valid():
        instance = form.save(commit=False)
        instance.user = request.user
        instance.save()
        return redirect('liste_ante_mortem')
    return render(request, 'sante_publique/ante_mortem_form.html', {'form': form, 'update': False})

@login_required
def modifier_ante_mortem(request, pk):
    instance = get_object_or_404(RegistreInspectionAnteMortem, pk=pk)
    form = RegistreInspectionAnteMortemForm(request.POST or None, instance=instance)
    if form.is_valid():
        form.save()
        return redirect('liste_ante_mortem')
    return render(request, 'sante_publique/ante_mortem_form.html', {'form': form, 'update': True})

@login_required
def supprimer_ante_mortem(request, pk):
    instance = get_object_or_404(RegistreInspectionAnteMortem, pk=pk)
    if request.method == 'POST':
        instance.delete()
        return redirect('liste_ante_mortem')
    return render(request, 'sante_publique/ante_mortem_confirm_delete.html', {'objet': instance})



@login_required
def liste_saisies_totales(request):
    enregistrements = RegistreSaisiesTotales.objects.all()
    return render(request, 'sante_publique/saisies_totales_liste.html', {'enregistrements': enregistrements})

@login_required
def ajouter_saisies_totales(request):
    form = RegistreSaisiesTotalesForm(request.POST or None)
    if form.is_valid():
        instance = form.save(commit=False)
        instance.user = request.user
        instance.save()
        return redirect('liste_saisies_totales')
    return render(request, 'sante_publique/saisies_totales_form.html', {'form': form, 'update': False})

@login_required
def modifier_saisies_totales(request, pk):
    instance = get_object_or_404(RegistreSaisiesTotales, pk=pk)
    form = RegistreSaisiesTotalesForm(request.POST or None, instance=instance)
    if form.is_valid():
        form.save()
        return redirect('liste_saisies_totales')
    return render(request, 'sante_publique/saisies_totales_form.html', {'form': form, 'update': True})

@login_required
def supprimer_saisies_totales(request, pk):
    instance = get_object_or_404(RegistreSaisiesTotales, pk=pk)
    if request.method == 'POST':
        instance.delete()
        return redirect('liste_saisies_totales')
    return render(request, 'sante_publique/saisies_totales_confirm_delete.html', {'objet': instance})

@login_required
def liste_saisies_organes(request):
    enregistrements = RegistreSaisiesOrganes.objects.all()
    return render(request, 'sante_publique/saisies_organes_liste.html', {'enregistrements': enregistrements})

@login_required
def ajouter_saisies_organes(request):
    form = RegistreSaisiesOrganesForm(request.POST or None)
    if form.is_valid():
        instance = form.save(commit=False)
        instance.user = request.user
        instance.save()
        return redirect('liste_saisies_organes')
    return render(request, 'sante_publique/saisies_organes_form.html', {'form': form, 'update': False})

@login_required
def modifier_saisies_organes(request, pk):
    instance = get_object_or_404(RegistreSaisiesOrganes, pk=pk)
    form = RegistreSaisiesOrganesForm(request.POST or None, instance=instance)
    if form.is_valid():
        form.save()
        return redirect('liste_saisies_organes')
    return render(request, 'sante_publique/saisies_organes_form.html', {'form': form, 'update': True})

@login_required
def supprimer_saisies_organes(request, pk):
    instance = get_object_or_404(RegistreSaisiesOrganes, pk=pk)
    if request.method == 'POST':
        instance.delete()
        return redirect('liste_saisies_organes')
    return render(request, 'sante_publique/saisies_organes_confirm_delete.html', {'objet': instance})


@login_required
def liste_inspections_viande(request):
    inspections = InspectionViande.objects.all().order_by('-date_inspection')
    return render(request, 'sante_publique/inspection_viande_liste.html', {'inspections': inspections})


@login_required
def ajouter_inspection_viande(request):
    if request.method == 'POST':
        form = InspectionViandeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('liste_inspections_viande')
    else:
        form = InspectionViandeForm()
    return render(request, 'sante_publique/inspection_viande_form.html', {'form': form, 'update': False})


@login_required
def modifier_inspection_viande(request, pk):
    inspection = get_object_or_404(InspectionViande, pk=pk)
    if request.method == 'POST':
        form = InspectionViandeForm(request.POST, instance=inspection)
        if form.is_valid():
            form.save()
            return redirect('liste_inspections_viande')
    else:
        form = InspectionViandeForm(instance=inspection)
    return render(request, 'sante_publique/inspection_viande_form.html', {'form': form, 'update': True})


@login_required
def supprimer_inspection_viande(request, pk):
    inspection = get_object_or_404(InspectionViande, pk=pk)
    if request.method == 'POST':
        inspection.delete()
        return redirect('liste_inspections_viande')
    return render(request, 'sante_publique/inspection_viande_confirm_delete.html', {'objet': inspection})




def get_filtered_queryset(queryset, periode_data, region):
    if region:
        queryset = queryset.filter(region=region)

    annee = int(periode_data.get("annee", datetime.today().year))
    if periode_data.get("periode_type") == "Hebdomadaire":
        semaine = int(periode_data.get("semaine"))
        date_debut = datetime.strptime(f"{annee}-W{semaine}-1", "%Y-W%W-%w")
        date_fin = date_debut + timedelta(days=6)
    elif periode_data.get("periode_type") == "Mensuel":
        mois = int(periode_data.get("mois"))
        date_debut = datetime(annee, mois, 1)
        if mois == 12:
            date_fin = datetime(annee + 1, 1, 1) - timedelta(days=1)
        else:
            date_fin = datetime(annee, mois + 1, 1) - timedelta(days=1)
    elif periode_data.get("periode_type") == "Trimestriel":
        trimestre = int(periode_data.get("trimestre"))
        date_debut = datetime(annee, 1 + (trimestre - 1) * 3, 1)
        date_fin = datetime(annee, 1 + trimestre * 3, 1) - timedelta(days=1) if trimestre < 4 else datetime(annee, 12, 31)
    elif periode_data.get("periode_type") == "Semestriel":
        semestre = int(periode_data.get("semestre"))
        date_debut = datetime(annee, 1, 1) if semestre == 1 else datetime(annee, 7, 1)
        date_fin = datetime(annee, 6, 30) if semestre == 1 else datetime(annee, 12, 31)
    else:  # Annuel
        date_debut = datetime(annee, 1, 1)
        date_fin = datetime(annee, 12, 31)

    return queryset.filter(date_enregistrement__range=(date_debut, date_fin))

@login_required
def dashboard_sante_publique(request):
    form = PeriodeRapportForm(request.POST or None)
    context = {"form": form}

    if request.method == "POST" and form.is_valid():
        region = form.cleaned_data.get("region")
        periode_data = form.cleaned_data

        abattages = get_filtered_queryset(RegistreAbattage.objects.all(), periode_data, region)
        inspections = get_filtered_queryset(RegistreInspectionAnteMortem.objects.all(), periode_data, region)
        saisies_totales = get_filtered_queryset(RegistreSaisiesTotales.objects.all(), periode_data, region)
        saisies_organes = get_filtered_queryset(RegistreSaisiesOrganes.objects.all(), periode_data, region)

        inspections_viande_qs = InspectionViande.objects.all()
        inspections_viande = get_filtered_queryset(inspections_viande_qs, periode_data, None)

        abattage_par_espece = abattages.values("espece__Espece").annotate(total=Sum("nombres"))
        abattage_par_commune = abattages.values("commune__Nom").annotate(total=Sum("nombres"))
        repartition_age = abattages.values("ages").annotate(total=Sum("nombres"))
        repartition_sexe = abattages.values("sexes").annotate(total=Sum("nombres"))

        anomalies_freq = inspections.values("anomalies").annotate(total=Count("anomalies")).order_by("-total")[:5]
        symptomes_freq = inspections.values("symptomes").annotate(total=Count("symptomes")).order_by("-total")[:5]

        motifs_saisies = saisies_totales.values("motifs_saisies").annotate(total=Count("id"))
        organes_saisies = saisies_organes.values("organes_saisis").annotate(total=Count("id"))

        aspect_carcasses = inspections_viande.values("aspect_carcasse").annotate(total=Count("aspect_carcasse"))
        organe_repartition = {
            "foie": inspections_viande.filter(foie="anomalie").count(),
            "poumons": inspections_viande.filter(poumons="anomalie").count(),
            "rate": inspections_viande.filter(rate="anomalie").count(),
            "coeur": inspections_viande.filter(coeur="anomalie").count(),
        }

        # Pagination
        abattage_qs = abattages.select_related("espece", "commune", "region")
        paginator_abattage = Paginator(abattage_qs, 10)
        page_abattage = request.GET.get("page_abattage")
        abattage_page_obj = paginator_abattage.get_page(page_abattage)

        inspection_qs = inspections.select_related("espece", "commune")
        paginator_inspection = Paginator(inspection_qs, 10)
        page_inspection = request.GET.get("page_inspection")
        inspection_page_obj = paginator_inspection.get_page(page_inspection)

        saisies_qs = saisies_totales.select_related("espece", "commune")
        paginator_saisies = Paginator(saisies_qs, 10)
        page_saisies = request.GET.get("page_saisies")
        saisies_page_obj = paginator_saisies.get_page(page_saisies)

        context.update({
            "total_animaux_abattus": abattages.aggregate(Sum("nombres"))['nombres__sum'] or 0,
            "valeur_totale": (abattages.aggregate(Sum("valeur_financiere"))['valeur_financiere__sum'] or 0) +
                             (saisies_totales.aggregate(Sum("valeur_financiere"))['valeur_financiere__sum'] or 0) +
                             (saisies_organes.aggregate(Sum("valeur_financiere"))['valeur_financiere__sum'] or 0),
            "total_anomalies": inspections.aggregate(Sum("nombres"))['nombres__sum'] or 0,
            "total_saisies_totales": saisies_totales.aggregate(Sum("nombres"))['nombres__sum'] or 0,
            "total_saisies_organes": saisies_organes.aggregate(Sum("nombres"))['nombres__sum'] or 0,
            "total_inspections": inspections_viande.count(),

            # Objets paginés
            "abattage_page_obj": abattage_page_obj,
            "inspection_page_obj": inspection_page_obj,
            "saisies_page_obj": saisies_page_obj,

            # Visualisation
            "abattage_par_espece": abattage_par_espece,
            "abattage_par_commune": abattage_par_commune,
            "repartition_age": repartition_age,
            "repartition_sexe": repartition_sexe,
            "anomalies_freq": anomalies_freq,
            "symptomes_freq": symptomes_freq,
            "motifs_saisies": motifs_saisies,
            "organes_saisies": organes_saisies,
            "aspect_carcasses": aspect_carcasses,
            "organe_repartition": organe_repartition
        })

    return render(request, "sante_publique/dashboard_sante_publique.html", context)

@login_required
def export_sante_publique_excel(request):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)  # Retirer la feuille par défaut

    def add_sheet(sheet_name, headers, rows):
        ws = wb.create_sheet(title=sheet_name)
        ws.append(headers)
        for row in rows:
            cleaned_row = []
            for cell in row:
                if hasattr(cell, 'tzinfo'):
                    cleaned_row.append(cell.replace(tzinfo=None))
                else:
                    cleaned_row.append(cell)
            ws.append(cleaned_row)

    # 1. Abattage
    abattage_headers = ['Date', 'Région', 'Département', 'Commune', 'Espèce', 'Âge', 'Sexe', 'Nombre', 'Poids (kg)', 'Valeur (FCFA)', 'Observations']
    abattage_rows = RegistreAbattage.objects.select_related("region", "departement", "commune", "espece").values_list(
        'date_enregistrement', 'region__Nom', 'departement__Nom', 'commune__Nom',
        'espece__Espece', 'ages', 'sexes', 'nombres', 'poids', 'valeur_financiere', 'observations'
    )
    add_sheet("Abattage", abattage_headers, abattage_rows)

    # 2. Inspection Ante-Mortem
    ante_headers = ['Date', 'Région', 'Département', 'Commune', 'Espèce', 'Anomalies', 'Symptômes', 'Nombre', 'Poids', 'Valeur', 'Observations']
    ante_rows = RegistreInspectionAnteMortem.objects.select_related("region", "departement", "commune", "espece").values_list(
        'date_enregistrement', 'region__Nom', 'departement__Nom', 'commune__Nom',
        'espece__Espece', 'anomalies', 'symptomes', 'nombres', 'poids', 'valeur_financiere', 'observations'
    )
    add_sheet("Inspection Ante-Mortem", ante_headers, ante_rows)

    # 3. Saisies Totales
    saisie_total_headers = ['Date', 'Région', 'Département', 'Commune', 'Espèce', 'Motifs', 'Nombre', 'Poids', 'Valeur', 'Observations']
    saisie_total_rows = RegistreSaisiesTotales.objects.select_related("region", "departement", "commune", "espece").values_list(
        'date_enregistrement', 'region__Nom', 'departement__Nom', 'commune__Nom',
        'espece__Espece', 'motifs_saisies', 'nombres', 'poids', 'valeur_financiere', 'observations'
    )
    add_sheet("Saisies Totales", saisie_total_headers, saisie_total_rows)

    # 4. Saisies Organes
    saisie_organe_headers = ['Date', 'Région', 'Département', 'Commune', 'Espèce', 'Organes Saisis', 'Motifs', 'Nombre', 'Poids', 'Valeur', 'Observations']
    saisie_organe_rows = RegistreSaisiesOrganes.objects.select_related("region", "departement", "commune", "espece").values_list(
        'date_enregistrement', 'region__Nom', 'departement__Nom', 'commune__Nom',
        'espece__Espece', 'organes_saisis', 'motifs_saisies_organes', 'nombres', 'poids', 'valeur_financiere', 'observations'
    )
    add_sheet("Saisies Organes", saisie_organe_headers, saisie_organe_rows)

    # 5. Inspection Viande
    inspection_headers = ['Date Inspection', 'Abattoir', 'Inspecteur', 'Espèce', 'État animal',
                          'Signes Anormaux', 'Autres signes', 'Aspect Carcasse', 'Poumons', 'Foie', 'Rate',
                          'Cœur', 'Anomalies Description', 'Observations', 'Signature']
    inspection_rows = InspectionViande.objects.select_related("espece").values_list(
        'date_inspection', 'abattoir', 'inspecteur', 'espece__Espece', 
        'etat_animal', 'signes_anormaux', 'autre_signe_anormal', 'aspect_carcasse',
        'poumons', 'foie', 'rate', 'coeur', 'description_anomalies', 'observations', 'signature_inspecteur'
    )
    add_sheet("Inspection Viande", inspection_headers, inspection_rows)

    # Réponse HTTP avec enregistrement du fichier
    response = HttpResponse(content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response['Content-Disposition'] = 'attachment; filename=sante_publique.xlsx'
    wb.save(response)
    return response