# lims/views_rapport_periodique.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, date
from typing import Dict, Any, Tuple
from calendar import monthrange

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum, DecimalField, F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.utils import timezone

from .models import (
    Demande, Analyse, Echantillon, TestCatalogue,
    SiteLabo, Maladie
)

# ----------------------------
# En-têtes par défaut (affichage + export)
# ----------------------------
HEADER_DEFAULT = {
    "org1": "BURKINA FASO<br><em>La patrie ou la Mort, nous Vaincrons</em>",
    "org2": "MINISTERE DE L' AGRICULTURE DES RESSOURCES ANIMALES ET HALIEUTIQUES– DGSV / Laboratoire National d’Élevage (LNE)",
    "code": "AHIS/LIMS/RAP-PER",
    "version": "1.0",
    "date_app": date(2025, 1, 1),
    "page_note": "Document interne",
}

# ----------------------------
# Helpers période & libellés
# ----------------------------

PERIODS = {
    "hebdo": "Hebdomadaire",
    "mensuel": "Mensuel",
    "trimestriel": "Trimestriel",
    "semestriel": "Semestriel",
    "annuel": "Annuel",
}

@dataclass
class Bounds:
    start: datetime
    end: datetime
    label: str
    numero: str
    titre: str

def _aware(dt: datetime) -> datetime:
    return timezone.make_aware(dt) if timezone.is_naive(dt) else dt

def _start_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)

def _end_of_day(dt: datetime) -> datetime:
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)

def _fr_date(d: datetime) -> str:
    return d.strftime("%d/%m/%Y")

def _period_bounds(period: str, ref: datetime) -> Bounds:
    ref = _aware(ref)
    y, m = ref.year, ref.month

    if period == "hebdo":
        monday = ref - timedelta(days=ref.weekday())
        sunday = monday + timedelta(days=6)
        start = _start_of_day(monday)
        end = _end_of_day(sunday)
        week_num = int(ref.strftime("%V"))
        return Bounds(start, end,
                      f"Semaine du {_fr_date(start)} au {_fr_date(end)}",
                      f"N°{week_num}",
                      "Rapport Hebdomadaire")

    if period == "mensuel":
        first = datetime(y, m, 1, tzinfo=ref.tzinfo)
        last = datetime(y, m, monthrange(y, m)[1], tzinfo=ref.tzinfo)
        start = _start_of_day(first)
        end = _end_of_day(last)
        return Bounds(start, end,
                      f"Mois de {ref.strftime('%B').capitalize()} {y}",
                      f"N°{m}",
                      "Rapport Mensuel")

    if period == "trimestriel":
        q = (m - 1) // 3 + 1
        first_month = (q - 1) * 3 + 1
        last_month = first_month + 2
        first = datetime(y, first_month, 1, tzinfo=ref.tzinfo)
        last = datetime(y, last_month, monthrange(y, last_month)[1], tzinfo=ref.tzinfo)
        start = _start_of_day(first)
        end = _end_of_day(last)
        return Bounds(start, end,
                      f"Trimestre {q} — {y}",
                      f"N°{q}",
                      "Rapport Trimestriel")

    if period == "semestriel":
        s = 1 if m <= 6 else 2
        first_month = 1 if s == 1 else 7
        last_month = 6 if s == 1 else 12
        first = datetime(y, first_month, 1, tzinfo=ref.tzinfo)
        last = datetime(y, last_month, monthrange(y, last_month)[1], tzinfo=ref.tzinfo)
        start = _start_of_day(first)
        end = _end_of_day(last)
        return Bounds(start, end,
                      f"Semestre {s} — {y}",
                      f"N°{s}",
                      "Rapport Semestriel")

    # annuel
    first = datetime(y, 1, 1, tzinfo=ref.tzinfo)
    last = datetime(y, 12, 31, tzinfo=ref.tzinfo)
    start = _start_of_day(first)
    end = _end_of_day(last)
    return Bounds(start, end,
                  f"Année {y}",
                  f"N°{y}",
                  "Rapport Annuel")

def _period_from_request(request: HttpRequest) -> Tuple[str, Bounds]:
    period = (request.GET.get("period") or "hebdo").lower()
    if period not in PERIODS:
        period = "hebdo"
    ref_str = request.GET.get("ref")
    if ref_str:
        try:
            ref = datetime.strptime(ref_str, "%Y-%m-%d")
            ref = _aware(ref)
        except Exception:
            ref = timezone.now()
    else:
        ref = timezone.now()
    return period, _period_bounds(period, ref)

def _label_maladie(m: Maladie | None) -> str:
    if not m:
        return "—"
    for att in ("Nom", "name", "nom", "Maladie"):
        if hasattr(m, att):
            val = getattr(m, att)
            if callable(val):
                try:
                    val = val()
                except Exception:
                    val = None
            if val:
                return str(val)
    return str(m)

# ----------------------------
# Agrégations (résumé)
# ----------------------------

def _reception_window_q(start: datetime, end: datetime) -> Q:
    """Fenêtre de réception: privilégie recu_le si présent, sinon retombe sur cree_le."""
    return Q(demande__recu_le__gte=start, demande__recu_le__lte=end) | (
        Q(demande__recu_le__isnull=True) & Q(demande__cree_le__gte=start, demande__cree_le__lte=end)
    )

def _donnees_generales(bounds):
    start, end = bounds.start, bounds.end
    sites = list(SiteLabo.objects.order_by("nom").values("id", "nom", "code"))

    recu_map = {
        x["demande__site_labo_id"]: x["c"]
        for x in (
            Echantillon.objects
            .filter(_reception_window_q(start, end))
            .values("demande__site_labo_id").annotate(c=Count("id"))
        )
    }

    ana_qs = Analyse.objects.filter(
        termine_le__isnull=False,
        termine_le__gte=start, termine_le__lte=end,
    )
    ana_map = {
        x["echantillon__demande__site_labo_id"]: x["n_ech"]
        for x in (
            ana_qs.values("echantillon__demande__site_labo_id")
                  .annotate(n_ech=Count("echantillon_id", distinct=True))
        )
    }

    montant_map = {
        x["echantillon__demande__site_labo_id"]: x["m"]
        for x in (
            ana_qs.values("echantillon__demande__site_labo_id")
                 .annotate(m=Sum(F("test__tarif_fcfa"),
                                 output_field=DecimalField(max_digits=14, decimal_places=2)))
        )
    }

    nc_map = {
        x["demande__site_labo_id"]: x["c"]
        for x in (
            Echantillon.objects
            .filter(_reception_window_q(start, end), conformite="non_conforme")
            .values("demande__site_labo_id").annotate(c=Count("id"))
        )
    }
    rec_ext_map = {
        x["demande__site_labo_id"]: x["c"]
        for x in (
            Echantillon.objects
            .filter(_reception_window_q(start, end), reception_externe=True)
            .values("demande__site_labo_id").annotate(c=Count("id"))
        )
    }
    env_ext_map = {
        x["demande__site_labo_id"]: x["c"]
        for x in (
            Echantillon.objects
            .filter(_reception_window_q(start, end), envoi_externe=True)
            .values("demande__site_labo_id").annotate(c=Count("id"))
        )
    }

    rows, tot_recu, tot_ana, tot_montant = [], 0, 0, 0
    for s in sites:
        sid = s["id"]
        r = int(recu_map.get(sid, 0))
        a = int(ana_map.get(sid, 0))
        montant = montant_map.get(sid, 0) or 0
        pct = (a / r * 100.0) if r > 0 else 0.0

        rows.append({
            "site": s["code"] or s["nom"],
            "recu": r,
            "analyse": a,
            "pct": pct,
            "nc": int(nc_map.get(sid, 0)),
            "rec_ext": int(rec_ext_map.get(sid, 0)),
            "env_ext": int(env_ext_map.get(sid, 0)),
            "montant": montant,
        })
        tot_recu += r
        tot_ana += a
        tot_montant += montant

    totals = {
        "site": "TOTAUX",
        "recu": tot_recu,
        "analyse": tot_ana,
        "pct": (tot_ana / tot_recu * 100.0) if tot_recu > 0 else 0.0,
        "nc": sum(r["nc"] for r in rows),
        "rec_ext": sum(r["rec_ext"] for r in rows),
        "env_ext": sum(r["env_ext"] for r in rows),
        "montant": tot_montant,
    }
    return {"rows": rows, "totals": totals}

def _positifs_par_laboratoire(bounds: Bounds) -> Dict[str, Any]:
    start, end = bounds.start, bounds.end
    qs = (Demande.objects
          .filter(suspicion_statut="confirmee",
                  suspicion_le__gte=start, suspicion_le__lte=end)
          .select_related("site_labo", "maladie_suspectee"))

    sites = list(SiteLabo.objects.order_by("nom").values("id", "code", "nom"))
    site_labels = {s["id"]: (s["code"] or s["nom"]) for s in sites}

    maladies_ids = set(qs.values_list("maladie_suspectee_id", flat=True))
    maladies = {m.id: _label_maladie(m) for m in Maladie.objects.filter(id__in=maladies_ids)}

    grid: Dict[tuple[int, int], int] = {}
    for d in qs:
        if not d.maladie_suspectee_id:
            continue
        key = (d.maladie_suspectee_id, d.site_labo_id)
        grid[key] = grid.get(key, 0) + 1

    rows = []
    for mid, mlabel in sorted(maladies.items(), key=lambda kv: kv[1].lower()):
        row = {"maladie": mlabel, "sites": [], "total": 0}
        for s in sites:
            c = grid.get((mid, s["id"]), 0)
            row["sites"].append({"site": site_labels[s["id"]], "c": c})
            row["total"] += c
        rows.append(row)

    totals = {"maladie": "TOTAUX", "sites": [], "total": 0}
    for s in sites:
        col_total = sum(grid.get((mid, s["id"]), 0) for mid in maladies.keys())
        totals["sites"].append({"site": site_labels[s["id"]], "c": col_total})
        totals["total"] += col_total

    return {"sites": [site_labels[s["id"]] for s in sites], "rows": rows, "totals": totals}

def _positifs_par_region(bounds: Bounds) -> Dict[str, Any]:
    """
    Colonnes = toutes les maladies présentes en base (Maladie).
    Valeurs = nb de demandes 'confirmées' dans la période, ventilées par (région, maladie).
    """
    start, end = bounds.start, bounds.end

    # Toutes les régions (lignes, même à 0)
    from Region.models import Region
    regions = list(Region.objects.all())

    def _region_label(obj) -> str:
        for att in ("Nom", "name", "nom"):
            if hasattr(obj, att):
                val = getattr(obj, att)
                if val:
                    return str(val)
        return str(obj)

    region_labels = {r.id: _region_label(r).strip() for r in regions}

    # Colonnes = toutes les maladies
    mal_objs = list(Maladie.objects.all())
    mal_cols = [(m.id, _label_maladie(m)) for m in mal_objs]
    mal_cols.sort(key=lambda kv: kv[1].lower())
    col_ids = [mid for (mid, _) in mal_cols]
    col_labels = [mlabel for (_, mlabel) in mal_cols]

    # Demandes confirmées dans la période
    qs = (
        Demande.objects
        .filter(
            suspicion_statut="confirmee",
            suspicion_le__gte=start, suspicion_le__lte=end,
            maladie_suspectee__isnull=False,
        )
        .select_related("region", "maladie_suspectee")
    )

    grid: Dict[tuple[int, int], int] = {}
    for d in qs:
        if not (d.region_id and d.maladie_suspectee_id):
            continue
        key = (d.region_id, d.maladie_suspectee_id)
        grid[key] = grid.get(key, 0) + 1

    rows = []
    for rid, rlabel in sorted(region_labels.items(), key=lambda kv: kv[1].lower()):
        row_cells = []
        total = 0
        for mid in col_ids:
            c = grid.get((rid, mid), 0)
            row_cells.append({"maladie": mid, "c": c})
            total += c
        rows.append({"region": rlabel, "maladies": row_cells, "total": total})

    totals = {"region": "TOTAUX", "maladies": [], "total": 0}
    for mid in col_ids:
        col_total = sum(grid.get((rid, mid), 0) for rid in region_labels.keys())
        totals["maladies"].append({"maladie": mid, "c": col_total})
        totals["total"] += col_total

    return {"maladies": col_labels, "rows": rows, "totals": totals}

def _indicateurs_LNE(bounds: Bounds) -> Dict[str, Any]:
    start, end = bounds.start, bounds.end

    site_lne = SiteLabo.objects.filter(code__iexact="LNE").first() or SiteLabo.objects.order_by("id").first()
    if not site_lne:
        return {
            "site": "LNE",
            "rows": [],
            "totals": {"recu": 0, "traite": 0, "nc": 0, "tests": 0, "sla": "0%"},
        }

    label_map = dict(TestCatalogue.SECTIONS)

    recu_total = (
        Echantillon.objects
        .filter(Q(demande__site_labo=site_lne) & _reception_window_q(start, end))
        .values("id").distinct().count()
    )

    rows = []
    tot_traite = 0
    tot_tests = 0
    tot_on_time = 0

    for code_section, lib_section in TestCatalogue.SECTIONS:
        recu_section = (
            Analyse.objects
            .filter(
                echantillon__demande__site_labo=site_lne,
                test__section=code_section,
            )
            .filter(
                Q(echantillon__demande__recu_le__gte=start, echantillon__demande__recu_le__lte=end) |
                (Q(echantillon__demande__recu_le__isnull=True) &
                 Q(echantillon__demande__cree_le__gte=start, echantillon__demande__cree_le__lte=end))
            )
            .values("echantillon_id").distinct().count()
        )

        a_qs = (
            Analyse.objects
            .filter(
                echantillon__demande__site_labo=site_lne,
                test__section=code_section,
                termine_le__isnull=False,
                termine_le__gte=start,
                termine_le__lte=end,
            )
        )

        nb_traites = a_qs.values("echantillon_id").distinct().count()
        nb_tests = a_qs.count()

        on_time = 0
        for termine_le, due in a_qs.values_list("termine_le", "echantillon__demande__date_echeance"):
            if termine_le and due and termine_le <= due:
                on_time += 1
        sla = f"{int(round((on_time / nb_tests * 100.0), 0))}%" if nb_tests > 0 else "0%"

        rows.append({
            "service": label_map.get(code_section, code_section),
            "recu": recu_section,
            "traite": nb_traites,
            "nc": 0,
            "tests": nb_tests,
            "sla": sla,
        })

        tot_traite += nb_traites
        tot_tests += nb_tests
        tot_on_time += on_time

    sla_tot = f"{int(round((tot_on_time / tot_tests * 100.0), 0))}%" if tot_tests > 0 else "0%"

    totals = {
        "recu": recu_total,
        "traite": tot_traite,
        "nc": 0,
        "tests": tot_tests,
        "sla": sla_tot,
    }

    return {"site": getattr(site_lne, "code", "LNE"), "rows": rows, "totals": totals}

# ----------------------------
# Vue principale + export PDF
# ----------------------------

@login_required
def rapport_periodique(request: HttpRequest) -> HttpResponse:
    period, bounds = _period_from_request(request)

    ctx_data = {
        "period": period,
        "periods": PERIODS,
        "bounds": bounds,
        "header": HEADER_DEFAULT,
        "general": _donnees_generales(bounds),
        "par_labo": _positifs_par_laboratoire(bounds),
        "par_region": _positifs_par_region(bounds),
        "ind_lne": _indicateurs_LNE(bounds),
    }

    qs = request.GET.copy()
    for k in ("format", "dl"):
        if k in qs:
            del qs[k]
    ctx_data["qs_no_fmt"] = qs.urlencode()

    fmt = (request.GET.get("format") or "html").lower()

    if fmt == "pdf":
        html = render_to_string("lims/rapports/periodique_export.html", ctx_data, request=request)
        filename = f"rapport_periodique_{bounds.titre.replace(' ', '_')}_{bounds.numero}.pdf".replace("—", "-")
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
            resp = HttpResponse(pdf_bytes, content_type="application/pdf")
            # Forcer le téléchargement
            resp["Content-Disposition"] = f'attachment; filename="{filename}"'
            return resp
        except Exception:
            return HttpResponse(html)

    return render(request, "lims/rapports/periodique.html", ctx_data)
