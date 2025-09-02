# materiel/views_doses.py  (ou dans views.py si tu préfères)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, models
from django.apps import apps

from .models import DotationDoseVaccin
from .forms import DotationDoseVaccinForm

Campagne = apps.get_model("Campagne", "Campagne")   # adapte la casse si besoin
Maladie  = apps.get_model("Maladie", "Maladie")     # idem

@login_required
def dotation_dose_list(request):
    qs = (DotationDoseVaccin.objects
          .select_related("campagne", "maladie", "user")
          .only("id", "quantite_doses", "date_dotation",
                "campagne__Campagne", "campagne__type_campagne",
                "maladie__Maladie", "user__username"))

    # filtres
    campagne_id = request.GET.get("campagne") or ""
    maladie_id  = request.GET.get("maladie") or ""
    d1          = request.GET.get("d1") or ""
    d2          = request.GET.get("d2") or ""
    q           = (request.GET.get("q") or "").strip()

    if campagne_id:
        qs = qs.filter(campagne_id=campagne_id)
    if maladie_id:
        qs = qs.filter(maladie_id=maladie_id)
    if d1 and d2:
        qs = qs.filter(date_dotation__range=[d1, d2])
    elif d1:
        qs = qs.filter(date_dotation__gte=d1)
    elif d2:
        qs = qs.filter(date_dotation__lte=d2)

    if q:
        qs = qs.filter(
            models.Q(campagne__Campagne__icontains=q) |
            models.Q(maladie__Maladie__icontains=q) |
            models.Q(observations__icontains=q)
        )

    paginator = Paginator(qs.order_by("-date_dotation", "campagne__Campagne", "maladie__Maladie"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "dotations": page_obj,
        "campagnes": Campagne.objects.only("id","Campagne","type_campagne","statut").order_by("-statut","-Campagne"),
        "maladies": Maladie.objects.only("id","Maladie").order_by("Maladie"),
        "campagne_id": campagne_id, "maladie_id": maladie_id,
        "d1": d1, "d2": d2, "q": q,
    }
    return render(request, "materiel/dose_list.html", ctx)

@login_required
def dotation_dose_create(request):
    form = DotationDoseVaccinForm(request.POST or None, request.FILES or None)
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user if request.user.is_authenticated else None
            try:
                obj.save()
            except IntegrityError:
                messages.error(request, "Une dotation (campagne/maladie/date) existe déjà.")
            else:
                messages.success(request, "Dotation en doses enregistrée.")
                return redirect("dose_list")
    return render(request, "materiel/dose_form.html", {"form": form})

@login_required
def dotation_dose_update(request, pk):
    obj = get_object_or_404(DotationDoseVaccin, pk=pk)
    form = DotationDoseVaccinForm(request.POST or None, request.FILES or None, instance=obj)
    if request.method == "POST":
        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                messages.error(request, "Conflit : dotation identique (campagne/maladie/date).")
            else:
                messages.success(request, "Dotation mise à jour.")
                return redirect("dose_list")
    return render(request, "materiel/dose_form.html", {"form": form, "obj": obj})

@login_required
def dotation_dose_delete(request, pk):
    obj = get_object_or_404(DotationDoseVaccin, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Dotation supprimée.")
        return redirect("dose_list")
    return render(request, "materiel/dose_confirm_delete.html", {"obj": obj})
