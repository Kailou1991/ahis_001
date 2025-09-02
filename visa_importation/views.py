# visa_importation/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from .models import FactureImportationVisee
from .forms import FactureImportationForm
from django.db.models import Q


def is_dsv(user):
    return user.groups.filter(name__in=[
        "Gestionnaire des Médicaments",
        "Santé publique"
    ]).exists()

def is_pif(user):
    return user.groups.filter(name__in=[
        "Services vétérinaires à l'aéroport",
        "Services vétérinaires au port"
    ]).exists()

def is_pif_aeroport(user):
    return user.groups.filter(name="Services vétérinaires à l'aéroport").exists()

def is_pif_port(user):
    return user.groups.filter(name="Services vétérinaires au port").exists()


# ------------------------- CRUD pour DSV -------------------------

@login_required

def ajouter_facture(request):
    if request.method == "POST":
        form = FactureImportationForm(request.POST, request.FILES)
        if form.is_valid():
            facture = form.save(commit=False)
            facture.vise_par_dsv = request.user
            facture.save()
            return redirect("liste_factures")
    else:
        form = FactureImportationForm()
    return render(request, "visa_importation/ajouter_facture.html", {"form": form})


@login_required

def liste_factures(request):
    factures = FactureImportationVisee.objects.all()
    return render(request, "visa_importation/liste_factures.html", {"factures": factures})

@login_required

@login_required
def liste_factures_non_controlees(request):
    factures = FactureImportationVisee.objects.filter(est_visa_pif=False)
    return render(request, "visa_importation/controle_liste.html", {"factures": factures})



# ------------------------ Validation par PIF ------------------------

@login_required
def valider_facture_pif(request, facture_id):
    facture = get_object_or_404(FactureImportationVisee, id=facture_id)
    if request.method == "POST":
        facture.est_visa_pif = True
        facture.date_visa_pif = timezone.now()
        facture.vise_par_pif = request.user
        facture.commentaire = request.POST.get("commentaire")

        if is_pif_aeroport(request.user):
            facture.origine_pif = "AÉROPORT"
        elif is_pif_port(request.user):
            facture.origine_pif = "PORT"

        facture.save()
        return redirect("tableau_bord_pif")
    return render(request, "visa_importation/valider_facture_pif.html", {"facture": facture})


# ------------------------ Tableau de bord PIF ------------------------

@login_required
def tableau_bord_pif(request):
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    factures = FactureImportationVisee.objects.all()

    if date_debut and date_fin:
        factures = factures.filter(
            Q(date_visa_dsv__range=[date_debut, date_fin]) |
            Q(date_visa_pif__range=[date_debut, date_fin])
        )

    factures_visees = factures.filter(est_visa_pif=True)
    factures_non_visees = factures.filter(est_visa_pif=False)

    return render(request, "visa_importation/dashboard_pif.html", {
        "visees": factures_visees,
        "non_visees": factures_non_visees,
        "date_debut": date_debut,
        "date_fin": date_fin,
    })