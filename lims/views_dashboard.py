# lims/views_dashboard.py
from __future__ import annotations
from io import BytesIO
from datetime import datetime, timedelta
from typing import Dict, Any, List

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum, F
from django.db.models.functions import TruncDate, TruncMonth, Coalesce
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone

from .models import Demande, Analyse, TestCatalogue, SiteLabo

# Matplotlib (rendu serveur PNG)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ---------- Helpers filtres & utilitaires ----------

def _parse_date(s: str | None, default: datetime) -> datetime:
    if not s:
        return default
    try:
        dt = datetime.strptime(s, "%Y-%m-%d")
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    except Exception:
        return default

def _filters(request) -> Dict[str, Any]:
    end_default = timezone.now()
    start_default = end_default - timedelta(days=30)

    start = _parse_date(request.GET.get("start"), start_default)
    end   = _parse_date(request.GET.get("end"), end_default)

    site_id   = (request.GET.get("site") or "").strip()
    section   = (request.GET.get("section") or "").strip()
    methode   = (request.GET.get("methode") or "").strip()
    suspicion = (request.GET.get("suspicion") or "").strip()

    # Filtres Demande (par date de création)
    q_d = Q(cree_le__gte=start, cree_le__lte=end)
    if site_id:
        q_d &= Q(site_labo_id=site_id)
    if suspicion:
        q_d &= Q(suspicion_statut=suspicion)

    # Filtres Analyse (via la période de création de la Demande associée)
    q_a = Q(echantillon__demande__cree_le__gte=start,
            echantillon__demande__cree_le__lte=end)
    if site_id:
        q_a &= Q(echantillon__demande__site_labo_id=site_id)
    if section:
        q_a &= Q(test__section=section)
    if methode:
        q_a &= Q(test__methode=methode)

    return {
        "start": start,
        "end": end,
        "site_id": site_id,
        "section": section,
        "methode": methode,
        "suspicion": suspicion,
        "q_d": q_d,
        "q_a": q_a,
        "qs": request.GET.urlencode(),  # pour re-propager aux <img src=...>
    }

def _date_range_list(start: datetime, end: datetime) -> list[datetime]:
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end   = end.replace(hour=0, minute=0, second=0, microsecond=0)
    cur = start
    out = []
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out

def _month_range_list(start: datetime, end: datetime) -> list[datetime]:
    """Liste des 1ers jours de chaque mois entre start et end (inclus)."""
    s = datetime(start.year, start.month, 1, tzinfo=start.tzinfo)
    e = datetime(end.year, end.month, 1, tzinfo=end.tzinfo)
    out = []
    cur = s
    while cur <= e:
        out.append(cur)
        # incrément mois
        y, m = cur.year, cur.month
        if m == 12:
            cur = cur.replace(year=y+1, month=1)
        else:
            cur = cur.replace(month=m+1)
    return out

_FR_MONTHS = {
    1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
    7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
}
def _fr_month_label(dt: datetime) -> str:
    return f"{_FR_MONTHS[dt.month]}_{dt.year}"

def _fullname_or_username(first: str | None, last: str | None, username: str | None) -> str:
    fn = (first or "").strip()
    ln = (last or "").strip()
    if fn or ln:
        return (fn + " " + ln).strip()
    return username or "—"


# ---------- Page Dashboard ----------

@login_required
def dashboard(request):
    f = _filters(request)
    now = timezone.now()

    # ---- KPIs Demandes
    d_qs = Demande.objects.filter(f["q_d"])
    total_demandes = d_qs.count()
    conclues = d_qs.exclude(suspicion_statut="non_evaluee").count()
    confirmees = d_qs.filter(suspicion_statut="confirmee").count()
    infirmees  = d_qs.filter(suspicion_statut="infirmee").count()

    # ---- KPIs Analyses
    a_qs = Analyse.objects.filter(f["q_a"])
    total_analyses = a_qs.count()
    terminees = a_qs.exclude(termine_le__isnull=True).count()

    # TAT médian (heures)
    durs = []
    for debute_le, termine_le in a_qs.values_list("debute_le", "termine_le"):
        if debute_le and termine_le:
            durs.append((termine_le - debute_le).total_seconds() / 3600.0)
    durs.sort()
    tat_median_h = durs[len(durs)//2] if durs else 0.0

    # SLA on-time vs late (terminées avant l’échéance)
    on_time = late = 0
    for termine_le, due in a_qs.values_list("termine_le", "echantillon__demande__date_echeance"):
        if not termine_le or not due:
            continue
        if termine_le <= due:
            on_time += 1
        else:
            late += 1

    # ---- Listes opérationnelles
    # Analyses en cours = démarrées non terminées
    analyses_en_cours = list(
        a_qs.filter(debute_le__isnull=False, termine_le__isnull=True)
            .values("id",
                    "echantillon__code_echantillon",
                    "test__code_test", "test__nom_test",
                    "analyste__first_name", "analyste__last_name", "analyste__username",
                    "debute_le", "echantillon__demande__date_echeance")
            .order_by("-debute_le")[:20]
    )
    for r in analyses_en_cours:
        r["analyste_label"] = _fullname_or_username(
            r["analyste__first_name"], r["analyste__last_name"], r["analyste__username"]
        )

    # Analyses en retard (non terminées et dues, OU terminées après échéance)
    raw_retard = list(
        a_qs.filter(
            Q(echantillon__demande__date_echeance__isnull=False) &
            (Q(termine_le__isnull=True, echantillon__demande__date_echeance__lt=now) |
             Q(termine_le__gt=F("echantillon__demande__date_echeance")))
        )
        .values("id",
                "echantillon__code_echantillon",
                "test__code_test", "test__nom_test",
                "analyste__first_name", "analyste__last_name", "analyste__username",
                "echantillon__demande__date_echeance", "termine_le")
        .order_by("echantillon__demande__date_echeance")[:50]
    )
    analyses_en_retard: List[dict] = []
    for r in raw_retard:
        due = r["echantillon__demande__date_echeance"]
        t   = r["termine_le"]
        if not due:
            continue
        if t:  # terminé en retard
            delta = t - due
        else:  # pas terminé, retard = now - due
            delta = now - due
        jours = max(delta.days, 0)
        r["jours_retard"] = jours
        r["analyste_label"] = _fullname_or_username(
            r["analyste__first_name"], r["analyste__last_name"], r["analyste__username"]
        )
        analyses_en_retard.append(r)

    # Analyses non affectées
    analyses_non_affectees = list(
        a_qs.filter(analyste__isnull=True)
            .values("id", "echantillon__code_echantillon",
                    "test__code_test", "test__nom_test", "echantillon__demande__cree_le")
            .order_by("-echantillon__demande__cree_le")[:20]
    )

    # ---- Agrégations Activité
    by_section = list(a_qs.values("test__section").annotate(c=Count("id")).order_by("-c"))
    by_methode = list(a_qs.values("test__methode").annotate(c=Count("id")).order_by("-c"))
    top_tests  = list(a_qs.values("test__code_test", "test__nom_test").annotate(c=Count("id")).order_by("-c")[:10])
    by_analyste = list(
        a_qs.values("analyste__first_name", "analyste__last_name", "analyste__username")
            .annotate(c=Count("id")).order_by("-c")[:12]
    )
    for r in by_analyste:
        r["label"] = _fullname_or_username(r["analyste__first_name"], r["analyste__last_name"], r["analyste__username"])

    # ---- Épidémiologie (sur Demandes) — champ libellé = Maladie.Maladie
    epi_qs = (
        d_qs.values("maladie_suspectee__id", "maladie_suspectee__Maladie")
           .annotate(
               nb=Count("id"),
               expo=Coalesce(Sum("effectif_troupeau"), 0),
               sick=Coalesce(Sum("nbre_animaux_malades"), 0),
               dead=Coalesce(Sum("nbre_animaux_morts"), 0),
           )
           .order_by("-nb")
    )
    epi_rows: List[Dict[str, Any]] = []
    for e in epi_qs:
        label = e["maladie_suspectee__Maladie"] or "—"
        expo = int(e["expo"] or 0)
        sick = int(e["sick"] or 0)
        dead = int(e["dead"] or 0)
        morbid = (sick / expo * 100.0) if expo > 0 else 0.0   # morbidité
        leth   = (dead / sick * 100.0) if sick > 0 else 0.0   # létalité
        mort   = (dead / expo * 100.0) if expo > 0 else 0.0   # mortalité
        epi_rows.append({
            "maladie": label, "nb": e["nb"], "expo": expo, "sick": sick, "dead": dead,
            "morbid": round(morbid, 1), "leth": round(leth, 1), "mort": round(mort, 1),
        })
    epi_top = epi_rows[:10]

    # ---- Clients
    clients_rows = list(
        d_qs.values("soumissionnaire__nom_complet")
           .annotate(nb=Count("id"))
           .order_by("-nb")[:10]
    )

    ctx = {
        "sites": SiteLabo.objects.order_by("nom"),
        "sections": TestCatalogue.SECTIONS,
        "methodes": TestCatalogue.METHODES,

        "default_start": f["start"].date().isoformat(),
        "default_end": f["end"].date().isoformat(),
        "qs": f["qs"],

        # KPIs
        "total_demandes": total_demandes,
        "conclues": conclues,
        "confirmees": confirmees,
        "infirmees": infirmees,
        "total_analyses": total_analyses,
        "terminees": terminees,
        "tat_median_h": round(tat_median_h, 1),
        "sla_on_time": on_time,
        "sla_late": late,

        # Listes
        "analyses_en_cours": analyses_en_cours,
        "analyses_en_retard": analyses_en_retard,
        "analyses_non_affectees": analyses_non_affectees,

        # Agrégations
        "by_section": by_section,
        "by_methode": by_methode,
        "top_tests": top_tests,
        "by_analyste": by_analyste,

        # Épidémio & Clients
        "epi_rows": epi_rows,
        "epi_top": epi_top,
        "clients_rows": clients_rows,
    }
    return render(request, "lims/dashboard.html", ctx)


# ---------- Graphes PNG (un <img> = une vue) ----------

def _render_png(fig) -> HttpResponse:
    buf = BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format="png")
    plt.close(fig)
    buf.seek(0)
    return HttpResponse(buf.getvalue(), content_type="image/png")

def _bar_colors(n: int):
    cmap = plt.cm.get_cmap('tab20', max(n, 1))
    return [cmap(i) for i in range(n)]

def _style_bar_chart(ax, bars, values, rotate=0):
    # Axe Y supprimé
    ax.yaxis.set_visible(False)
    # Lignes de cadre légères
    for spine in ["left", "right"]:
        ax.spines[spine].set_visible(False)
    # Étiquettes de données
    max_v = max(values) if values else 0
    for i, b in enumerate(bars):
        v = values[i]
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + (max_v * 0.02 if max_v else 0.1),
                str(v), ha="center", va="bottom", fontsize=9)
    if rotate:
        ax.tick_params(axis="x", labelrotation=rotate)


from datetime import date

@login_required
def chart_series(request):
    """Demandes par mois (barres) — libellés: NomMois_Année."""
    f = _filters(request)

    qs = (
        Demande.objects.filter(f["q_d"])
        .annotate(m=TruncMonth("cree_le"))
        .values("m")
        .annotate(c=Count("id"))
        .order_by("m")
    )

    # Normalise toutes les clés au 1er du mois en type 'date'
    counts = {date(x["m"].year, x["m"].month, 1): x["c"] for x in qs}

    months = _month_range_list(f["start"], f["end"])  # renvoie des datetimes (1er de chaque mois)
    month_keys = [date(m.year, m.month, 1) for m in months]  # mêmes clés que 'counts'
    labels = [_fr_month_label(m) for m in months]            # ex: "Août_2025"
    values = [counts.get(k, 0) for k in month_keys]

    fig, ax = plt.subplots(figsize=(9, 2.8), dpi=140)
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=_bar_colors(len(values)))
    ax.set_title("Demandes par mois")
    ax.set_xlabel("Mois")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20)
    _style_bar_chart(ax, bars, values, rotate=0)
    return _render_png(fig)


@login_required
def chart_sections(request):
    f = _filters(request)
    qs = (Analyse.objects.filter(f["q_a"])
          .values("test__section").annotate(c=Count("id")).order_by("-c"))
    label_map = dict(TestCatalogue.SECTIONS)
    labels = [label_map.get(x["test__section"], x["test__section"] or "—") for x in qs]
    values = [x["c"] for x in qs]

    fig, ax = plt.subplots(figsize=(6.8, 3.0), dpi=140)
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=_bar_colors(len(values)))
    ax.set_title("Analyses par section")
    ax.set_xlabel("Section")
    ax.set_xticks(x, labels)
    _style_bar_chart(ax, bars, values, rotate=15)
    return _render_png(fig)

@login_required
def chart_methods(request):
    f = _filters(request)
    qs = (Analyse.objects.filter(f["q_a"])
          .values("test__methode").annotate(c=Count("id")).order_by("-c"))
    label_map = dict(TestCatalogue.METHODES)
    labels = [label_map.get(x["test__methode"], x["test__methode"] or "—") for x in qs]
    values = [x["c"] for x in qs]

    fig, ax = plt.subplots(figsize=(6.8, 3.0), dpi=140)
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=_bar_colors(len(values)))
    ax.set_title("Analyses par méthode")
    ax.set_xlabel("Méthode")
    ax.set_xticks(x, labels)
    _style_bar_chart(ax, bars, values, rotate=20)
    return _render_png(fig)

@login_required
def chart_top_tests(request):
    f = _filters(request)
    qs = (Analyse.objects.filter(f["q_a"])
          .values("test__nom_test").annotate(c=Count("id")).order_by("-c")[:10])
    labels = [x["test__nom_test"] or "—" for x in qs]
    values = [x["c"] for x in qs]

    fig, ax = plt.subplots(figsize=(8.5, 3.2), dpi=140)
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=_bar_colors(len(values)))
    ax.set_title("Top 10 tests")
    ax.set_xlabel("Test")
    ax.set_xticks(x, labels)
    _style_bar_chart(ax, bars, values, rotate=30)
    return _render_png(fig)

@login_required
def chart_analysts(request):
    f = _filters(request)
    qs = (Analyse.objects.filter(f["q_a"])
          .values("analyste__first_name", "analyste__last_name", "analyste__username")
          .annotate(c=Count("id"))
          .order_by("-c")[:12])
    labels = [
        _fullname_or_username(x["analyste__first_name"], x["analyste__last_name"], x["analyste__username"])
        for x in qs
    ]
    values = [x["c"] for x in qs]

    fig, ax = plt.subplots(figsize=(8.5, 3.2), dpi=140)
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=_bar_colors(len(values)))
    ax.set_title("Analyses par analyste")
    ax.set_xlabel("Analyste")
    ax.set_xticks(x, labels)
    _style_bar_chart(ax, bars, values, rotate=30)
    return _render_png(fig)

@login_required
def chart_diseases(request):
    f = _filters(request)
    qs = (Demande.objects.filter(f["q_d"])
          .values("maladie_suspectee__Maladie")
          .annotate(c=Count("id")).order_by("-c")[:10])
    labels = [x["maladie_suspectee__Maladie"] or "—" for x in qs]
    values = [x["c"] for x in qs]

    fig, ax = plt.subplots(figsize=(8.5, 3.2), dpi=140)
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=_bar_colors(len(values)))
    ax.set_title("Top 10 maladies (demandes)")
    ax.set_xlabel("Maladie")
    ax.set_xticks(x, labels)
    _style_bar_chart(ax, bars, values, rotate=30)
    return _render_png(fig)

@login_required
def chart_clients(request):
    f = _filters(request)
    qs = (Demande.objects.filter(f["q_d"])
          .values("soumissionnaire__nom_complet")
          .annotate(c=Count("id")).order_by("-c")[:10])
    labels = [x["soumissionnaire__nom_complet"] or "—" for x in qs]
    values = [x["c"] for x in qs]

    fig, ax = plt.subplots(figsize=(8.5, 3.2), dpi=140)
    x = list(range(len(labels)))
    bars = ax.bar(x, values, color=_bar_colors(len(values)))
    ax.set_title("Top 10 clients (demandes)")
    ax.set_xlabel("Client")
    ax.set_xticks(x, labels)
    _style_bar_chart(ax, bars, values, rotate=30)
    return _render_png(fig)

@login_required
def chart_sla(request):
    f = _filters(request)
    on_time = late = 0
    qs = (Analyse.objects.filter(f["q_a"])
          .values_list("termine_le", "echantillon__demande__date_echeance"))
    for termine_le, due in qs:
        if not termine_le or not due:
            continue
        if termine_le <= due:
            on_time += 1
        else:
            late += 1

    vals = [on_time, late]
    labels = ["À l'heure", "En retard"]
    if on_time == 0 and late == 0:
        vals, labels = [1], ["Aucune donnée"]

    fig, ax = plt.subplots(figsize=(4.2, 4.2), dpi=140)
    ax.pie(vals, labels=labels, autopct="%1.0f%%" if sum(vals) > 0 else None, startangle=90)
    ax.set_title("SLA")
    return _render_png(fig)
