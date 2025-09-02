# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List, Tuple

from django.conf import settings
from django.core.mail import send_mail
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.timezone import now

from .models import (
    VaccinationSn,                         # parent
    VaccinationSnChild0c8ff1d1 as VChild,  # enfant (vaccinations)
)
from generated_apps.objectif_sn.models import (
    ObjectifSn,
    ObjectifSnChild0c8ff1d1 as OChild,     # enfant (objectifs)
)

from alerts.models import DestinataireAlerte         # destinataires en base
from materiel.models import DotationDoseVaccin       # doses livrées

# ----- Constantes -----
MAL_KOBO = "maladie_masse"      # champ libellé maladie côté Kobo (enfants)
MAL_DOT  = "maladie__Maladie"   # champ libellé maladie côté DotationDoseVaccin


# --------------------------------- Temps ---------------------------------
def last_iso_week_range() -> Tuple[date, date, str]:
    """Semaine ISO précédente (lundi..dimanche) + label 'YYYY-Www'."""
    today = now().date()
    y, w, _ = today.isocalendar()
    monday_this = date.fromisocalendar(y, w, 1)
    monday_prev = monday_this - timedelta(days=7)
    sunday_prev = monday_prev + timedelta(days=6)
    y_prev, w_prev, _ = monday_prev.isocalendar()
    label = f"Semaine {y_prev}-W{w_prev:02d}"
    return monday_prev, sunday_prev, label


# -------------------------- Campagne (libellé) ---------------------------
def detect_latest_campaign_name() -> str | None:
    """
    Dernière campagne (non vide) selon la date de soumission la plus récente,
    côté Kobo (parents objectifs / vaccinations).
    """
    last_v = (
        VaccinationSn.objects
        .exclude(campagne__isnull=True).exclude(campagne="")
        .order_by("-submission_time")
        .values_list("campagne", flat=True)
        .first()
    )
    last_o = (
        ObjectifSn.objects
        .exclude(campagne__isnull=True).exclude(campagne="")
        .order_by("-submission_time")
        .values_list("campagne", flat=True)
        .first()
    )
    return last_v or last_o


# ------------------------------ Utilitaires ------------------------------
def _norm(s: str | None) -> str:
    """Normalise les libellés maladies pour faire matcher toutes les sources."""
    return (s or "—").strip().upper()

def _i(v) -> int:
    """cast int avec fallback 0"""
    try:
        return int(v or 0)
    except Exception:
        return 0


# ------------------------- Calculs agrégés (Kobo) ------------------------
def compute_alert_metrics_kobo(campagne_name: str, end_day: date) -> tuple[list[dict], dict]:
    """
    Calcule par maladie :
      - objectif  = somme OChild.effectif_cible
      - eligible  = somme OChild.effectif_elligible
      - vaccines  = somme (VChild.vaccine_public + vaccine_prive) jusqu’à end_day
      - doses     = somme DotationDoseVaccin.quantite_doses jusqu’à end_day
    Retourne (per_maladie, global_line).
    """
    # Objectifs & éligibles (enfants ObjectifSn)
    obj_qs = (
        OChild.objects
        .select_related("parent")
        .filter(parent__campagne__iexact=campagne_name)
        .values(MAL_KOBO)
        .annotate(
            objectif=Coalesce(Sum("effectif_cible"), 0),
            eligible=Coalesce(Sum("effectif_elligible"), 0),
        )
    )
    obj_map: Dict[str, dict] = {
        _norm(r[MAL_KOBO]): {"objectif": _i(r["objectif"]), "eligible": _i(r["eligible"])}
        for r in obj_qs
    }

    # Vaccinations (enfants VaccinationSn)
    vac_qs = (
        VChild.objects
        .select_related("parent")
        .filter(parent__campagne__iexact=campagne_name,
                parent__submission_time__date__lte=end_day)
        .values(MAL_KOBO)
        .annotate(
            v_pub=Coalesce(Sum("vaccine_public"), 0),
            v_pri=Coalesce(Sum("vaccine_prive"), 0),
        )
    )
    vac_map: Dict[str, int] = {
        _norm(r[MAL_KOBO]): _i(r["v_pub"]) + _i(r["v_pri"])
        for r in vac_qs
    }

    # Doses livrées (DotationDoseVaccin – repérées par maladie FK)
    doses_qs = (
        DotationDoseVaccin.objects
        .filter(campagne__Campagne__iexact=campagne_name,
                date_dotation__lte=end_day)
        .values(MAL_DOT)
        .annotate(doses=Coalesce(Sum("quantite_doses"), 0))
    )
    dose_map: Dict[str, int] = {_norm(r[MAL_DOT]): _i(r["doses"]) for r in doses_qs}

    # Fusion des clés maladies
    all_mals = sorted(set(obj_map) | set(vac_map) | set(dose_map))

    per_maladie: List[dict] = []
    g_obj = g_elig = g_vac = g_dose = 0

    for mal in all_mals:
        O = obj_map.get(mal, {}).get("objectif", 0)
        E = obj_map.get(mal, {}).get("eligible", 0)
        V = vac_map.get(mal, 0)
        D = dose_map.get(mal, 0)

        taux_real = round((V / O) * 100, 2) if O else 0
        taux_couv = round((V / E) * 100, 2) if E else 0
        taux_app  = round((D / O) * 100, 2) if O else 0

        per_maladie.append({
            "maladie": mal,  # libellé normalisé (UPPER)
            "objectif": O, "eligible": E,
            "vaccines": V, "doses": D,
            "taux_real": taux_real,
            "taux_couv": taux_couv,
            "taux_app":  taux_app,
        })

        g_obj  += O
        g_elig += E
        g_vac  += V
        g_dose += D

    global_line = {
        "objectif": g_obj, "eligible": g_elig, "vaccines": g_vac, "doses": g_dose,
        "taux_real": round((g_vac / g_obj) * 100, 2) if g_obj else 0,
        "taux_couv": round((g_vac / g_elig) * 100, 2) if g_elig else 0,
        "taux_app":  round((g_dose / g_obj) * 100, 2) if g_obj else 0,
    }
    return per_maladie, global_line


# ----------------------------- Rendu HTML -----------------------------
def _tag(value, th):
    if th is None:
        return f"{value}"
    try:
        v = float(value)
    except Exception:
        return f"{value}"
    color = "#dc3545" if v < th else "#198754"
    return f'<span style="color:{color}; font-weight:600">{v}</span>'

def _fmt_int(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n)

def render_html_email_kobo(campagne_name: str, label_periode: str,
                           per_maladie: List[dict], global_line: dict,
                           thresholds: dict | None = None) -> str:
    thresholds = thresholds or {}
    th_real = thresholds.get("real")
    th_couv = thresholds.get("couv")
    th_app  = thresholds.get("app")

    rows = ""
    for r in per_maladie:
        rows += f"""
<tr>
  <td>{r['maladie']}</td>
  <td style="text-align:right">{_fmt_int(r['objectif'])}</td>
  <td style="text-align:right">{_fmt_int(r['eligible'])}</td>
  <td style="text-align:right">{_fmt_int(r['vaccines'])}</td>
  <td style="text-align:right">{_fmt_int(r['doses'])}</td>
  <td style="text-align:right">{_tag(r['taux_real'], th_real)}%</td>
  <td style="text-align:right">{_tag(r['taux_couv'], th_couv)}%</td>
  <td style="text-align:right">{_tag(r['taux_app'], th_app)}%</td>
</tr>"""

    g = global_line
    total_html = f"""
<tr style="font-weight:700;background:#f6f6f6">
  <td>Total</td>
  <td style="text-align:right">{_fmt_int(g['objectif'])}</td>
  <td style="text-align:right">{_fmt_int(g['eligible'])}</td>
  <td style="text-align:right">{_fmt_int(g['vaccines'])}</td>
  <td style="text-align:right">{_fmt_int(g['doses'])}</td>
  <td style="text-align:right">{_tag(g['taux_real'], th_real)}%</td>
  <td style="text-align:right">{_tag(g['taux_couv'], th_couv)}%</td>
  <td style="text-align:right">{_tag(g['taux_app'], th_app)}%</td>
</tr>"""

    return f"""
<h3>Alerte CAMVAC – {campagne_name} – {label_periode}</h3>
<p>Rappel des indicateurs cumulés depuis le début de la campagne jusqu’à cette période :</p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-family:Arial; font-size:13px; width:100%;">
  <thead style="background:#efefef">
    <tr>
      <th style="text-align:left">Maladie</th>
      <th style="text-align:right">Objectif</th>
      <th style="text-align:right">Éligible</th>
      <th style="text-align:right">Vaccinés</th>
      <th style="text-align:right">Doses livrées</th>
      <th style="text-align:right">Taux réalisation</th>
      <th style="text-align:right">Taux couverture</th>
      <th style="text-align:right">Taux approvisionnement</th>
    </tr>
  </thead>
  <tbody>
    {rows}
    {total_html}
  </tbody>
</table>
"""


# ------------------------------ Destinataires ------------------------------
def _recipient_emails() -> List[str]:
    """
    1) settings.CAMVAC_ALERT_RECIPIENTS si défini
    2) sinon, tous DestinataireAlerte actifs pour 'Vaccination'
    """
    cfg = getattr(settings, "CAMVAC_ALERT_RECIPIENTS", None)
    if cfg:
        return list(cfg)
    return list(
        DestinataireAlerte.objects
        .filter(actif=True, formulaire="Vaccination")
        .values_list("email", flat=True)
    )


# ------------------------------ Envoi email ------------------------------
def send_alert_email_kobo(campagne_name: str | None = None,
                          thresholds: dict | None = None,
                          dry_run: bool = False,
                          to_override: List[str] | None = None) -> dict:
    """
    Envoie l’alerte hebdomadaire. Si campagne_name est None, on détecte la dernière.
    thresholds ex: {"real":40, "couv":50, "app":60}
    """
    start, end, label = last_iso_week_range()

    if not campagne_name:
        campagne_name = detect_latest_campaign_name()
    if not campagne_name:
        return {"ok": False, "reason": "Aucune campagne détectée", "preview": ""}

    per_maladie, global_line = compute_alert_metrics_kobo(campagne_name, end)
    html = render_html_email_kobo(
        campagne_name, label, per_maladie, global_line,
        thresholds or getattr(settings, "CAMVAC_ALERT_THRESHOLDS", None)
    )

    recipients = to_override or _recipient_emails()
    subject = f"[CAMVAC] Alerte hebdomadaire – {campagne_name} – {label}"
    from email.utils import formataddr
    from_email = formataddr(("Notification AHIS", getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@example.org")))
    result = {
        "ok": True,
        "subject": subject,
        "recipients": recipients,
        "preview": html[:2000],
        "counts": {
            "rows": len(per_maladie),
            "objectif": global_line.get("objectif", 0),
            "vaccines": global_line.get("vaccines", 0),
        }
    }

    if dry_run or not recipients:
        result["sent"] = 0
        result["note"] = "dry-run ou aucun destinataire"
        return result

    sent = send_mail(
        subject=subject,
        message="",
        from_email=from_email,
        recipient_list=recipients,
        html_message=html,
        fail_silently=False,
    )
    result["sent"] = sent
    return result
