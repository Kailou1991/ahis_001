# -*- coding: utf-8 -*-
# generated_apps/surveillance_sn/views_export_map.py
from __future__ import annotations

import json, os, calendar, datetime as dt
from datetime import date, timedelta
from typing import Optional, Dict, Tuple

from django import forms
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, Value, IntegerField
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from openpyxl import Workbook

from .models import (
    SurveillanceSn as SParent,
    SurveillanceSnChild783b28ae as SChild,
)

# =========================
# Période & session helpers
# =========================
def _calculate_date_range(periode_type: str, annee: int, form) -> tuple[Optional[date], Optional[date]]:
    today = date.today()
    if periode_type == 'Hebdomadaire':
        w = int(form.cleaned_data['semaine']); start = date.fromisocalendar(annee, w, 1); end = start + timedelta(days=6)
        return start, min(end, today)
    if periode_type == 'Mensuel':
        m = int(form.cleaned_data['mois']); last = calendar.monthrange(annee, m)[1]
        return date(annee, m, 1), min(date(annee, m, last), today)
    if periode_type == 'Trimestriel':
        t = int(form.cleaned_data['trimestre']); m1, m2 = {1:(1,3),2:(4,6),3:(7,9),4:(10,12)}.get(t,(1,3))
        last = calendar.monthrange(annee, m2)[1]
        return date(annee, m1, 1), min(date(annee, m2, last), today)
    if periode_type == 'Semestriel':
        s = int(form.cleaned_data['semestre'])
        if s == 1:
            last = calendar.monthrange(annee, 6)[1]; return date(annee,1,1), min(date(annee,6,last), today)
        last = calendar.monthrange(annee,12)[1]; return date(annee,7,1), min(date(annee,12,last), today)
    if periode_type == 'Annuel':
        return date(annee,1,1), min(date(annee,12,31), today)
    return None, None


def _session_region_dept_names(request) -> tuple[Optional[str], Optional[str]]:
    region_name = depart_name = None
    try:
        region_id = request.session.get('region_id')
        depart_id = request.session.get('departement_id')
        if region_id:
            from Region.models import Region
            region_name = Region.objects.filter(id=region_id).values_list("Nom", flat=True).first()
        if depart_id:
            from Departement.models import Departement
            depart_name = Departement.objects.filter(id=depart_id).values_list("Nom", flat=True).first()
    except Exception:
        pass
    return region_name, depart_name


# =========================
# Formulaire GET
# =========================
class PeriodeRapportForm(forms.Form):
    PERIODES = (('Hebdomadaire','Hebdomadaire'), ('Mensuel','Mensuel'),
                ('Trimestriel','Trimestriel'), ('Semestriel','Semestriel'),
                ('Annuel','Annuel'))
    periode_type = forms.ChoiceField(choices=PERIODES, initial='Mensuel',
                                     widget=forms.Select(attrs={'class':'form-control'}))
    annee = forms.IntegerField(initial=date.today().year, min_value=2000, max_value=2100,
                               widget=forms.NumberInput(attrs={'class':'form-control'}))
    semaine = forms.IntegerField(required=False, min_value=1, max_value=53,
                                 widget=forms.NumberInput(attrs={'class':'form-control'}))
    mois = forms.IntegerField(required=False, min_value=1, max_value=12,
                              widget=forms.NumberInput(attrs={'class':'form-control'}))
    trimestre = forms.IntegerField(required=False, min_value=1, max_value=4,
                                   widget=forms.NumberInput(attrs={'class':'form-control'}))
    semestre = forms.IntegerField(required=False, min_value=1, max_value=2,
                                  widget=forms.NumberInput(attrs={'class':'form-control'}))
    region = forms.ChoiceField(required=False, choices=[("", "Toutes les régions")],
                               widget=forms.Select(attrs={'class':'form-control'}))
    maladie = forms.ChoiceField(required=False, choices=[("", "Toutes les maladies")],
                                widget=forms.Select(attrs={'class':'form-control'}))

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)  # <— récupère request
        super().__init__(*args, **kwargs)

        base_qs = SParent.objects.all()

        # restreint au périmètre session (si défini)
        region_nm = depart_nm = None
        if request:
            try:
                region_nm, depart_nm = _session_region_dept_names(request)
                if region_nm:
                    base_qs = base_qs.filter(grp3_region__iexact=region_nm)
                if depart_nm:
                    base_qs = base_qs.filter(grp3_departement__iexact=depart_nm)
            except Exception:
                pass

        regions = (base_qs.exclude(grp3_region__isnull=True).exclude(grp3_region="")
                   .values_list("grp3_region", flat=True).distinct().order_by("grp3_region"))
        maladies = (base_qs.exclude(grp5_qmad1__isnull=True).exclude(grp5_qmad1="")
                    .values_list("grp5_qmad1", flat=True).distinct().order_by("grp5_qmad1"))

        self.fields["region"].choices  = [("", "Toutes les régions")]  + [(r, r) for r in regions]
        self.fields["maladie"].choices = [("", "Toutes les maladies")] + [(m, m) for m in maladies]

        # Optionnel: pré-sélectionner la région de session quand la page est chargée en GET sans choix utilisateur
        if request and request.method == "GET" and region_nm:
            self.fields["region"].initial = region_nm

    def clean(self):
        c = super().clean(); p = c.get('periode_type')
        if p == 'Hebdomadaire' and not c.get('semaine'): self.add_error('semaine', "Indique la semaine (1–53).")
        if p == 'Mensuel' and not c.get('mois'): self.add_error('mois', "Indique le mois (1–12).")
        if p == 'Trimestriel' and not c.get('trimestre'): self.add_error('trimestre', "Indique le trimestre (1–4).")
        if p == 'Semestriel' and not c.get('semestre'): self.add_error('semestre', "Indique le semestre (1–2).")
        return c



# =========================
# Agrégats enfants & coords
# =========================
SENS_EXPR  = Coalesce(F("totaltroupeau"), F("effectif_total_troup_st_de_tot"), Value(0), output_field=IntegerField())
MORTS_EXPR = Coalesce(F("effectif_animaux_morts_calcule"), F("calcul_animaux_morts"), Value(0), output_field=IntegerField())
MAL_EXPR   = Coalesce(F("total_malade"), Value(0))

def _extract_latlon(parent: SParent) -> tuple[Optional[float], Optional[float]]:
    data = parent.geojson
    try:
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, (list, tuple)) and len(data) >= 2:
            lat = float(data[0]); lon = float(data[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return lat, lon
    except Exception:
        pass
    return None, None


# =========================
# Vue export + carte
# =========================
@login_required
def export_surv_excel(request: HttpRequest) -> HttpResponse:
    region_session_name, depart_session_name = _session_region_dept_names(request)
    form = PeriodeRapportForm(request.GET or None,request=request)

    parents = SParent.objects.all()
    if region_session_name:
        parents = parents.filter(grp3_region__iexact=region_session_name)
    if depart_session_name:
        parents = parents.filter(grp3_departement__iexact=depart_session_name)

    start_date = end_date = None
    region_choice = maladie_choice = ""

    if form.is_valid():
        periode_type = form.cleaned_data['periode_type']
        annee = int(form.cleaned_data['annee'])
        start_date, end_date = _calculate_date_range(periode_type, annee, form)

        if start_date and end_date:
            parents = parents.filter(grp1_date_signalement__range=(start_date, end_date))

        region_choice = (form.cleaned_data.get('region') or "").strip()
        maladie_choice = (form.cleaned_data.get('maladie') or "").strip()
        if region_choice:
            parents = parents.filter(grp3_region__iexact=region_choice)
        if maladie_choice:
            parents = parents.filter(grp5_qmad1__iexact=maladie_choice)

    # Export ?
    if (request.GET.get('export') or "").lower() in ("1", "true", "xlsx"):
        return _build_surv_xlsx(parents)

    # Sinon: carte
    map_html = generer_carte_surv(parents)
    ctx = {
        "form": form,
        "map_html": map_html,
        "start_date": start_date, "end_date": end_date,
        "region_choice": region_choice, "maladie_choice": maladie_choice,
        "region_session_name": region_session_name, "depart_session_name": depart_session_name,
    }
    return render(request, "surveillance_sn/export_surv.html", ctx)


# =========================
# Excel helper (tz naive)
# =========================
def _to_naive_datetime(value):
    if isinstance(value, dt.datetime):
        if timezone.is_aware(value):
            return timezone.make_naive(value, timezone.get_current_timezone())
        return value
    return value

def _cell(value):
    v = _to_naive_datetime(value)
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return v


# =========================
# Build XLSX – TOUS CHAMPS
# =========================
def _build_surv_xlsx(parents_qs):
    """
    Onglet 1 'Surveillance' = tous les champs du parent + lat/lon (geojson) + agrégats enfants.
    Onglet 2 'Grp6_items'  = tous les champs de l'enfant + quelques champs contexte du parent.
    """
    # Pré-agrégats enfants par parent
    sums = (SChild.objects.filter(parent__in=parents_qs)
            .values("parent_id")
            .annotate(exp=Sum(SENS_EXPR), mal=Sum(MAL_EXPR), dcd=Sum(MORTS_EXPR)))
    amap: Dict[int, Dict] = {r["parent_id"]: r for r in sums}

    # Tous les enfants liés
    children_qs = SChild.objects.select_related("parent").filter(parent__in=parents_qs)

    # Workbook
    wb = Workbook()
    ws_parent = wb.active
    ws_parent.title = "Surveillance"
    ws_child = wb.create_sheet("Grp6_items")

    # ===== Onglet PARENT =====
    parent_fields = [f for f in SParent._meta.concrete_fields]  # ordre du modèle
    parent_headers = [f.name for f in parent_fields] + ["lat_geojson", "lon_geojson", "agg_exposes", "agg_malades", "agg_morts"]
    ws_parent.append(parent_headers)

    for p in parents_qs.iterator():
        row = []
        for f in parent_fields:
            # pour FK éventuels: .attname (ex: parent_id) sinon .name
            attr = getattr(p, getattr(f, "attname", f.name))
            row.append(_cell(attr))
        lat, lon = _extract_latlon(p)
        a = amap.get(p.id, {})
        row.extend([_cell(lat), _cell(lon), int(a.get("exp") or 0), int(a.get("mal") or 0), int(a.get("dcd") or 0)])
        ws_parent.append(row)

    # ===== Onglet ENFANT =====
    child_fields = [f for f in SChild._meta.concrete_fields]
    child_headers = [f.name for f in child_fields] + [
        # contexte parent utile
        "parent_grp1_date_signalement", "parent_grp1_date_rapportage",
        "parent_grp3_region", "parent_grp3_departement", "parent_grp3_commune",
        "parent_grp3_nom_du_village", "parent_grp5_qmad1", "parent_instance_id",
        "parent_submission_time", "parent_submitted_by", "parent_status"
    ]
    ws_child.append(child_headers)

    for c in children_qs.iterator():
        row = []
        for f in child_fields:
            attr = getattr(c, getattr(f, "attname", f.name))
            row.append(_cell(attr))
        p = c.parent
        row.extend([
            _cell(p.grp1_date_signalement), _cell(p.grp1_date_rapportage),
            _cell(p.grp3_region), _cell(p.grp3_departement), _cell(p.grp3_commune),
            _cell((p.grp3_nom_du_village or "").strip()), _cell(p.grp5_qmad1), _cell(p.instance_id),
            _cell(p.submission_time), _cell(p.submitted_by), _cell(p.status),
        ])
        ws_child.append(row)

    # Réponse
    resp = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    resp['Content-Disposition'] = 'attachment; filename=surveillance_full.xlsx'
    wb.save(resp)
    return resp


# =========================
# Carte (points via geojson)
# =========================
def generer_carte_surv(parents_qs) -> str:
    """
    Carte groupée par maladie (parent.grp5_qmad1).
    Coordonnées UNIQUEMENT issues de parent.geojson = [lat, lon].
    """
    from collections import defaultdict
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    from folium import Map, TileLayer, GeoJson, Circle, Element

    # Aggreg enfants
    sums = (SChild.objects.filter(parent__in=parents_qs)
            .values("parent_id")
            .annotate(exp=Sum(SENS_EXPR), mal=Sum(MAL_EXPR), dcd=Sum(MORTS_EXPR)))
    amap: Dict[int, Dict] = {r["parent_id"]: r for r in sums}

    by_maladie = defaultdict(list)
    coords = []
    for p in parents_qs:
        lat, lon = _extract_latlon(p)
        if lat is not None and lon is not None:
            coords.append((lat, lon))
            by_maladie[p.grp5_qmad1 or "—"].append((p, lat, lon))

    center = [14.5, -14.5]
    if coords:
        center = [sum(y for y, _ in coords)/len(coords), sum(x for _, x in coords)/len(coords)]

    m = Map(location=center, zoom_start=6, control_scale=True)
    TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr='&copy; CartoDB', name='CartoDB Positron', control=False
    ).add_to(m)

    # Contexte Sénégal (optionnel)
    try:
        countries_path = os.path.join('static', 'geo', 'countries.geojson')
        if os.path.exists(countries_path):
            with open(countries_path, 'r', encoding='utf-8') as f:
                geo_data = json.load(f)
            sn = next((ft for ft in geo_data.get('features', [])
                       if ft.get('properties', {}).get('ADMIN') == 'Senegal'
                       or ft.get('properties', {}).get('name') == 'Senegal'), None)
            if sn:
                GeoJson(sn, name='Sénégal',
                        style_function=lambda x: {'fillColor':'#ffffff','color':'#000','weight':1.2,'fillOpacity':0.05}
                        ).add_to(m)
    except Exception:
        pass

    maladies = list(by_maladie.keys())
    cmap = cm.get_cmap('tab20', max(1, len(maladies)))
    color_map = {mal: mcolors.to_hex(cmap(i)) for i, mal in enumerate(maladies)}

    # Légende
    legend = ['''
    <style>
      #custom-legend{width:100%;background:#fff;border-top:1px solid #ccc;padding:8px 14px;
      font-size:13px;z-index:9999;position:relative;max-height:160px;overflow-y:auto;}
      #custom-legend .legend-title{font-weight:700;text-align:center;margin:4px 0 8px;}
      #custom-legend .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:6px 14px;}
      #custom-legend .item{display:flex;align-items:center;}
      #custom-legend .sq{width:14px;height:14px;border-radius:2px;margin-right:6px;display:inline-block}
    </style>
    <div id="custom-legend"><div class="legend-title">Légende – Maladies</div><div class="grid">
    ''']
    for mal in maladies:
        legend.append(f'<div class="item"><span class="sq" style="background:{color_map[mal]}"></span>{mal}</div>')
    legend.append('</div></div>')
    m.get_root().html.add_child(Element(''.join(legend)))

    # Points
    for mal, items in by_maladie.items():
        color = color_map.get(mal, "#3b82f6")
        for (p, lat, lon) in items:
            a = amap.get(p.id, {})
            exp = int(a.get("exp") or 0); malades = int(a.get("mal") or 0); morts = int(a.get("dcd") or 0)
            commune = p.grp3_commune or "-"; region = p.grp3_region or "-"
            loc = (p.grp3_nom_du_village or "").strip() or (p.grp3_lieususpicion or "-")
            when = p.grp1_date_signalement.strftime("%d/%m/%Y") if p.grp1_date_signalement else "-"
            popup = (f"<b>Maladie :</b> {mal}<br>"
                     f"<b>Date :</b> {when}<br>"
                     f"<b>Localité :</b> {loc} ({commune}, {region})<br>"
                     f"<b>Exposés/Malades/Morts :</b> {exp}/{malades}/{morts}")
            Circle(location=[lat, lon], radius=12000, color=color, fill=True, fill_color=color,
                   weight=1, popup=popup).add_to(m)

    # Style
    m.get_root().html.add_child(Element("""
    <style>
      #map {height: calc(100vh - 180px) !important; width: 100vw !important; margin:0 !important;}
      .folium-map {height: 100% !important;}
    </style>
    """))
    return m._repr_html_()
