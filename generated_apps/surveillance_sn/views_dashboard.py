# generated_apps/surveillance_sn/views_dashboard.py
from __future__ import annotations
# -*- coding: utf-8 -*-

import io, base64, calendar
from datetime import date, timedelta

from django import forms
from django.contrib.auth.decorators import login_required
from django.db.models import (
    Sum, Count, F, Value, IntegerField, DurationField, ExpressionWrapper, DateTimeField
)
from django.db.models.functions import Coalesce, TruncMonth, Cast
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .models import (
    SurveillanceSn as SParent,
    SurveillanceSnChild783b28ae as SChild,
)

# ===========================
#   Formulaire filtres
# ===========================
class PeriodeRapportForm(forms.Form):
    PERIODES = (
        ('Hebdomadaire', 'Hebdomadaire'),
        ('Mensuel', 'Mensuel'),
        ('Trimestriel', 'Trimestriel'),
        ('Semestriel', 'Semestriel'),
        ('Annuel', 'Annuel'),
    )
    periode_type = forms.ChoiceField(
        choices=PERIODES, initial='Mensuel',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    annee = forms.IntegerField(
        initial=date.today().year, min_value=2000, max_value=2100,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    semaine = forms.IntegerField(required=False, min_value=1, max_value=53,
                                 widget=forms.NumberInput(attrs={'class': 'form-control'}))
    mois = forms.IntegerField(required=False, min_value=1, max_value=12,
                              widget=forms.NumberInput(attrs={'class': 'form-control'}))
    trimestre = forms.IntegerField(required=False, min_value=1, max_value=4,
                                   widget=forms.NumberInput(attrs={'class': 'form-control'}))
    semestre = forms.IntegerField(required=False, min_value=1, max_value=2,
                                  widget=forms.NumberInput(attrs={'class': 'form-control'}))

    # Listes déroulantes (valeurs libres Kobo)
    region = forms.ChoiceField(
        required=False,
        choices=[("", "Toutes les régions")],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    maladie = forms.ChoiceField(
        required=False,
        choices=[("", "Toutes les maladies")],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        # ➜ récupère 'request' sans le passer à BaseForm
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)

        # Base queryset
        base_qs = SParent.objects.all()

        # ➜ restreint au périmètre session si présent
        if request:
            try:
                rid = request.session.get('region_id')
                did = request.session.get('departement_id')

                region_nm = None
                depart_nm = None

                if rid:
                    from Region.models import Region
                    region_nm = (Region.objects
                                 .filter(id=rid)
                                 .values_list('Nom', flat=True)
                                 .first())
                if did:
                    from Departement.models import Departement
                    depart_nm = (Departement.objects
                                 .filter(id=did)
                                 .values_list('Nom', flat=True)
                                 .first())

                if region_nm:
                    base_qs = base_qs.filter(grp3_region__iexact=region_nm)
                if depart_nm:
                    base_qs = base_qs.filter(grp3_departement__iexact=depart_nm)
            except Exception:
                # on ne bloque pas la construction du formulaire si un import échoue
                pass

        # Alimente les choices à partir du QS (éventuellement restreint)
        regions = (base_qs
                   .exclude(grp3_region__isnull=True).exclude(grp3_region="")
                   .values_list("grp3_region", flat=True)
                   .distinct().order_by("grp3_region"))
        maladies = (base_qs
                    .exclude(grp5_qmad1__isnull=True).exclude(grp5_qmad1="")
                    .values_list("grp5_qmad1", flat=True)
                    .distinct().order_by("grp5_qmad1"))

        self.fields["region"].choices  = [("", "Toutes les régions")]  + [(r, r) for r in regions]
        self.fields["maladie"].choices = [("", "Toutes les maladies")] + [(m, m) for m in maladies]

    def clean(self):
        cleaned = super().clean()
        p = cleaned.get('periode_type')
        if p == 'Hebdomadaire' and not cleaned.get('semaine'):
            self.add_error('semaine', "Indique la semaine (1–53).")
        if p == 'Mensuel' and not cleaned.get('mois'):
            self.add_error('mois', "Indique le mois (1–12).")
        if p == 'Trimestriel' and not cleaned.get('trimestre'):
            self.add_error('trimestre', "Indique le trimestre (1–4).")
        if p == 'Semestriel' and not cleaned.get('semestre'):
            self.add_error('semestre', "Indique le semestre (1–2).")
        return cleaned


# ===========================
#   Utilitaires période
# ===========================
def calculate_date_range(periode_type: str, annee: int, form: PeriodeRapportForm, today: date):
    if periode_type == 'Hebdomadaire':
        w = int(form.cleaned_data['semaine'])
        start = date.fromisocalendar(annee, w, 1)
        end = start + timedelta(days=6)
        return start, min(end, today)
    if periode_type == 'Mensuel':
        m = int(form.cleaned_data['mois'])
        last = calendar.monthrange(annee, m)[1]
        start = date(annee, m, 1)
        end = date(annee, m, last)
        return start, min(end, today)
    if periode_type == 'Trimestriel':
        t = int(form.cleaned_data['trimestre'])
        m1, m2 = {1:(1,3),2:(4,6),3:(7,9),4:(10,12)}.get(t, (1,3))
        last = calendar.monthrange(annee, m2)[1]
        start = date(annee, m1, 1); end = date(annee, m2, last)
        return start, min(end, today)
    if periode_type == 'Semestriel':
        s = int(form.cleaned_data['semestre'])
        if s == 1:
            last = calendar.monthrange(annee, 6)[1]; start = date(annee,1,1); end = date(annee,6,last)
        else:
            last = calendar.monthrange(annee,12)[1]; start = date(annee,7,1); end = date(annee,12,last)
        return start, min(end, today)
    if periode_type == 'Annuel':
        return date(annee,1,1), min(date(annee,12,31), today)
    return None, None


# ===========================
#   Agrégations & images
# ===========================
SENS_EXPR = Coalesce(F("totaltroupeau"), F("effectif_total_troup_st_de_tot"), Value(0), output_field=IntegerField())
MORTS_EXPR = Coalesce(F("effectif_animaux_morts_calcule"), F("calcul_animaux_morts"), Value(0), output_field=IntegerField())
MAL_EXPR   = Coalesce(F("total_malade"), Value(0))

def _fmt_int(v):
    try:
        return int(v or 0)
    except Exception:
        return 0

def _make_bar_png(labels, values, title, xlabel="", ylabel="", rotate_x=0, tight=True, figsize=(7.5, 4.0)):
    if not labels:
        return None
    from matplotlib import cm
    n = len(values)
    cmap = cm.get_cmap('tab20', max(1, n))  # palette multi-couleurs
    colors = [cmap(i) for i in range(n)]

    fig, ax = plt.subplots(figsize=figsize)
    ax.bar(range(n), values, color=colors, edgecolor='white', linewidth=0.7)
    ax.set_title(title)
    if xlabel: ax.set_xlabel(xlabel)
    if ylabel: ax.set_ylabel(ylabel)
    ax.set_xticks(range(n))
    ax.set_xticklabels(labels, rotation=rotate_x, ha='right' if rotate_x else 'center')

    y_offset = (max(values) if values else 1) * 0.02
    for i, v in enumerate(values):
        ax.text(i, v + y_offset, f'{v}', ha='center', fontsize=8)

    ax.grid(axis='y', linestyle='--', alpha=0.3)
    if tight: fig.tight_layout()
    buf = io.BytesIO(); fig.savefig(buf, format='png', dpi=140); plt.close(fig)
    buf.seek(0); b64 = base64.b64encode(buf.read()).decode('utf-8'); buf.close()
    return b64

def build_rates_png(total_exposes, total_malades, total_morts):
    letalite  = (total_morts / total_malades) * 100 if total_malades else 0.0
    morbidite = (total_malades / total_exposes) * 100 if total_exposes else 0.0
    mortalite = (total_morts   / total_exposes) * 100 if total_exposes else 0.0
    labels = ['Létalité', 'Morbidité', 'Mortalité']
    values = [round(letalite,2), round(morbidite,2), round(mortalite,2)]
    img = _make_bar_png(labels, values, "Taux globaux (%)", ylabel="Pourcentage")
    return img, {"letalite": letalite, "morbidite": morbidite, "mortalite": mortalite}

def img_by_region(parents_qs):
    data = (parents_qs.values("grp3_region")
            .annotate(n=Count("id"))
            .order_by("-n", "grp3_region"))
    labels = [(r["grp3_region"] or "—") for r in data]
    values = [int(r["n"] or 0) for r in data]
    return _make_bar_png(labels, values, "Foyers par région", "Région", "Foyers", rotate_x=30)

def img_by_maladie(parents_qs, top=12):
    data = (parents_qs.values("grp5_qmad1")
            .annotate(n=Count("id"))
            .order_by("-n", "grp5_qmad1")[:top])
    labels = [(r["grp5_qmad1"] or "—") for r in data]
    values = [int(r["n"] or 0) for r in data]
    return _make_bar_png(labels, values, "Foyers par maladie (top)", "Maladie", "Foyers", rotate_x=30)

def img_monthly_trend(parents_qs):
    data = (parents_qs.annotate(mois=TruncMonth("grp1_date_signalement"))
                     .values("mois")
                     .annotate(n=Count("id"))
                     .order_by("mois"))
    labels = [m["mois"].strftime("%Y-%m") if m["mois"] else "—" for m in data]
    values = [int(m["n"] or 0) for m in data]
    return _make_bar_png(labels, values, "Foyers par mois", "Mois", "Foyers", rotate_x=30)

def img_hist_malades(children_qs):
    data = (children_qs
            .annotate(mois=TruncMonth("parent__grp1_date_signalement"))
            .values("mois")
            .annotate(mal=Sum(MAL_EXPR))
            .order_by("mois"))
    labels = [m["mois"].strftime("%Y-%m") if m["mois"] else "—" for m in data]
    values = [int(m["mal"] or 0) for m in data]
    return _make_bar_png(labels, values, "Cas malades par mois", "Mois", "Cas", rotate_x=30)

def img_by_departement(parents_qs, top=15):
    data = (parents_qs.values("grp3_departement")
            .annotate(n=Count("id")).order_by("-n", "grp3_departement")[:top])
    labels = [(r["grp3_departement"] or "—") for r in data]
    values = [int(r["n"] or 0) for r in data]
    return _make_bar_png(labels, values, "Foyers par département (top)", "Département", "Foyers", rotate_x=30)

def table_maladie_summary(children_qs):
    agg = (children_qs
           .values("parent__grp5_qmad1")
           .annotate(
               exp=Sum(SENS_EXPR),
               mal=Sum(MAL_EXPR),
               dcd=Sum(MORTS_EXPR),
               foy=Count("parent_id", distinct=True),
           )
           .order_by("-mal", "parent__grp5_qmad1"))
    rows = []
    for r in agg:
        rows.append({
            "maladie": r["parent__grp5_qmad1"] or "—",
            "foyers":  _fmt_int(r["foy"]),
            "exposes": _fmt_int(r["exp"]),
            "malades": _fmt_int(r["mal"]),
            "morts":   _fmt_int(r["dcd"]),
        })
    return rows

def table_maladie_summary_commune(parents_qs):
    data = (parents_qs.values("grp3_region", "grp3_commune")
            .annotate(n=Count("id"))
            .order_by("-n", "grp3_region", "grp3_commune")[:50])
    return [{
        "region":  d["grp3_region"] or "—",
        "commune": d["grp3_commune"] or "—",
        "foyers":  int(d["n"] or 0),
    } for d in data]


# ===========================
#   Accès autorisé (adapte)
# ===========================
def group_required(*groups):
    def _decorator(view):
        return view
    return _decorator


# ===========================
#   Vue principale dashboard
# ===========================
# AJOUT EN HAUT DU FICHIER
from data_initialization.scop import scope_q_text
@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires',
                'Administrateur Régional','Administrateur Départemental',
                'Animateur de la Surveillance','Directeur de la Santé Animale')
def dashboard_surveillance(request: HttpRequest) -> HttpResponse:
    # (facultatif) on garde ces libellés juste pour l'affichage
    region_id = request.session.get('region_id')
    departement_id = request.session.get('departement_id')
    region_session_name = depart_session_name = None
    try:
        if region_id:
            from Region.models import Region
            region_session_name = Region.objects.filter(id=region_id).values_list('Nom', flat=True).first()
        if departement_id:
            from Departement.models import Departement
            depart_session_name = Departement.objects.filter(id=departement_id).values_list('Nom', flat=True).first()
    except Exception:
        pass

    # 👉 PASSER LA REQUEST AU FORM (pour restreindre les choix de région)
    form = PeriodeRapportForm(request.POST or None, request=request)

    start_date = end_date = None
    region_choice = ""
    maladie_choice = ""

    # 👉 APPLIQUER LE SCOPE DÈS LA BASE QUERY (région/département depuis la session)
    scope = scope_q_text(
        request,
        region_text_field="grp3_region",
        departement_text_field="grp3_departement",
    )
    parents = SParent.objects.filter(scope)

    # Filtres soumis dans le formulaire
    if request.method == 'POST' and form.is_valid():
        periode_type = form.cleaned_data['periode_type']
        annee = int(form.cleaned_data['annee'])
        region_choice = (form.cleaned_data.get('region') or "").strip()
        maladie_choice = (form.cleaned_data.get('maladie') or "").strip()

        start_date, end_date = calculate_date_range(periode_type, annee, form, date.today())
        if start_date and end_date:
            parents = parents.filter(grp1_date_signalement__range=(start_date, end_date))
        if region_choice:
            parents = parents.filter(grp3_region__iexact=region_choice)
        if maladie_choice:
            parents = parents.filter(grp5_qmad1__iexact=maladie_choice)

    # Enfants liés
    children = SChild.objects.select_related("parent").filter(parent__in=parents)

    # KPI globaux
    agg = children.aggregate(
        exposes=Sum(SENS_EXPR),
        malades=Sum(MAL_EXPR),
        morts=Sum(MORTS_EXPR),
    )
    total_exposes = _fmt_int(agg.get("exposes"))
    total_malades = _fmt_int(agg.get("malades"))
    total_morts   = _fmt_int(agg.get("morts"))
    total_foyers  = parents.values("id").distinct().count()

    # Délai médian (CAST date -> datetime)
    deltas_qs = (
        parents
        .exclude(grp1_date_signalement__isnull=True)
        .exclude(submission_time__isnull=True)
        .annotate(_signal_dt=Cast('grp1_date_signalement', DateTimeField()))
        .annotate(delay=ExpressionWrapper(F('submission_time') - F('_signal_dt'),
                                          output_field=DurationField()))
        .values_list('delay', flat=True)
    )
    delays = [int(d.total_seconds() // 86400) for d in deltas_qs if d is not None]
    delays.sort()
    median_delay = delays[len(delays)//2] if delays else None

    # Graphiques (matplotlib -> base64)
    img_rates, taux_dict = build_rates_png(total_exposes, total_malades, total_morts)
    img_region = img_maladie = img_trend = img_hist = img_departement = None
    if parents.exists():
        img_region = img_by_region(parents)
        img_maladie = img_by_maladie(parents)
        img_trend = img_monthly_trend(parents)
        img_departement = img_by_departement(parents)
    if children.exists():
        img_hist = img_hist_malades(children)

    # Tableaux
    maladie_summary = table_maladie_summary(children)
    maladie_summary_commune = table_maladie_summary_commune(parents)

    context = {
        "form": form,

        # KPI
        "total_foyers": total_foyers,
        "total_exposes": total_exposes,
        "total_malades": total_malades,
        "total_morts": total_morts,
        "median_delay": median_delay,

        # Images b64
        "img_rates": img_rates,
        "img_region": img_region,
        "img_maladie": img_maladie,
        "img_trend": img_trend,
        "img_hist": img_hist,
        "img_departement": img_departement,

        # Taux numériques
        "taux_letalite":  taux_dict.get("letalite", 0.0),
        "taux_morbidite": taux_dict.get("morbidite", 0.0),
        "taux_mortalite": taux_dict.get("mortalite", 0.0),

        # Tableaux
        "maladie_summary": maladie_summary,
        "maladie_summary_commune": maladie_summary_commune,

        # Filtres choisis
        "start_date": start_date,
        "end_date": end_date,
        "region_choice": region_choice,
        "maladie_choice": maladie_choice,

        # Infos session (affichage bandeau)
        "region_session_name": region_session_name,
        "depart_session_name": depart_session_name,
    }
    return render(request, "surveillance_sn/dashboard.html", context)
