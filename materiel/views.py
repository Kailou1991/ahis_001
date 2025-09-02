from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone
from django.apps import apps

from .models import TypeMateriel, Dotation
from .forms import DotationForm

# éviter les imports circulaires
Region = apps.get_model("Region", "Region")

# ------------------- LISTE + FILTRES -------------------
@login_required
def dotation_list(request):
    # éviter import circulaire
    from django.apps import apps
    Campagne = apps.get_model("Campagne", "Campagne")

    qs = (
        Dotation.objects
        .select_related("region", "type_materiel", "campagne", "user")
        .only(
            "id", "quantite", "date_dotation", "observations",
            "region__Nom", "type_materiel__nom",
            "campagne__Campagne", "campagne__type_campagne",
            "user__username"
        )
    )

    campagne_id = request.GET.get("campagne") or ""
    region_id   = request.GET.get("region") or ""
    type_id     = request.GET.get("type") or ""
    d1          = request.GET.get("d1") or ""
    d2          = request.GET.get("d2") or ""
    q           = (request.GET.get("q") or "").strip()

    if campagne_id:
        qs = qs.filter(campagne_id=campagne_id)
    if region_id:
        qs = qs.filter(region_id=region_id)
    if type_id:
        qs = qs.filter(type_materiel_id=type_id)

    if d1 and d2:
        qs = qs.filter(date_dotation__range=[d1, d2])
    elif d1:
        qs = qs.filter(date_dotation__gte=d1)
    elif d2:
        qs = qs.filter(date_dotation__lte=d2)

    if q:
        qs = qs.filter(
            Q(type_materiel__nom__icontains=q) |
            Q(region__Nom__icontains=q) |
            Q(campagne__Campagne__icontains=q) |
            Q(observations__icontains=q)
        )

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "dotations": page_obj,
        "campagnes": Campagne.objects.only("id", "Campagne", "type_campagne", "statut").order_by("-statut", "-Campagne"),
        "regions": Region.objects.only("id", "Nom").order_by("Nom"),
        "types": TypeMateriel.objects.only("id", "nom").order_by("nom"),
        "campagne_id": campagne_id,
        "region_id": region_id,
        "type_id": type_id,
        "d1": d1,
        "d2": d2,
        "q": q,
    }
    return render(request, "materiel/dotation_list.html", ctx)

# ------------------- CREATE -------------------
@login_required
def dotation_create(request):
    if request.method == "POST":
        form = DotationForm(request.POST, request.FILES)
        # Trier les querysets pour un rendu propre si erreur de validation
        form.fields["region"].queryset = Region.objects.order_by("Nom")
        form.fields["type_materiel"].queryset = TypeMateriel.objects.order_by("nom")

        if form.is_valid():
            obj = form.save(commit=False)
            obj.user = request.user if request.user.is_authenticated else None
            try:
                obj.save()
            except IntegrityError:
                messages.error(request,
                    "Une dotation pour ce type, cette région et cette date existe déjà.")
            else:
                messages.success(request, "Dotation enregistrée avec succès.")
                return redirect("dotation_list")
    else:
        form = DotationForm(initial={"date_dotation": timezone.now().date()})
        form.fields["region"].queryset = Region.objects.order_by("Nom")
        form.fields["type_materiel"].queryset = TypeMateriel.objects.order_by("nom")

    return render(request, "materiel/dotation_form.html", {"form": form})

# ------------------- UPDATE -------------------
@login_required
def dotation_update(request, pk):
    obj = get_object_or_404(Dotation, pk=pk)
    if request.method == "POST":
        form = DotationForm(request.POST, request.FILES, instance=obj)
        form.fields["region"].queryset = Region.objects.order_by("Nom")
        form.fields["type_materiel"].queryset = TypeMateriel.objects.order_by("nom")

        if form.is_valid():
            try:
                form.save()
            except IntegrityError:
                messages.error(request,
                    "Conflit d’unicité : une dotation identique existe déjà.")
            else:
                messages.success(request, "Dotation mise à jour.")
                return redirect("dotation_list")
    else:
        form = DotationForm(instance=obj)
        form.fields["region"].queryset = Region.objects.order_by("Nom")
        form.fields["type_materiel"].queryset = TypeMateriel.objects.order_by("nom")

    return render(request, "materiel/dotation_form.html", {"form": form, "obj": obj})

# ------------------- DELETE -------------------
@login_required
def dotation_delete(request, pk):
    obj = get_object_or_404(Dotation, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Dotation supprimée.")
        return redirect("dotation_list")
    return render(request, "materiel/dotation_confirm_delete.html", {"obj": obj})

# ------------------- TypeMateriel CRUD (formulaires Bootstrap) -------------------
from django import forms
class TypeMaterielForm(forms.ModelForm):
    class Meta:
        model = TypeMateriel
        fields = ["nom"]
        widgets = {"nom": forms.TextInput(attrs={"class": "form-control"})}

@login_required
def type_list(request):
    q = (request.GET.get("q") or "").strip()
    qs = TypeMateriel.objects.all()
    if q:
        qs = qs.filter(nom__icontains=q)
    paginator = Paginator(qs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(request, "materiel/type_materiel_list.html", {"types": page_obj, "q": q})

@login_required
def type_create(request):
    form = TypeMaterielForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            form.add_error("nom", "Ce type existe déjà.")
        else:
            messages.success(request, "Type de matériel créé.")
            return redirect("dotation_create")
    return render(request, "materiel/type_materiel_form.html", {"form": form})

@login_required
def type_update(request, pk):
    obj = get_object_or_404(TypeMateriel, pk=pk)
    form = TypeMaterielForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        try:
            form.save()
        except IntegrityError:
            form.add_error("nom", "Un autre type porte déjà ce nom.")
        else:
            messages.success(request, "Type de matériel mis à jour.")
            return redirect("type_list")
    return render(request, "materiel/type_materiel_form.html", {"form": form, "obj": obj})

@login_required
def type_delete(request, pk):
    obj = get_object_or_404(TypeMateriel, pk=pk)
    if request.method == "POST":
        obj.delete()
        messages.success(request, "Type de matériel supprimé.")
        return redirect("type_list")
    return render(request, "materiel/type_materiel_confirm_delete.html", {"obj": obj})

