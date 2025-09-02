# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import List
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape

from alerts.models import DestinataireAlerte
from .models import SurveillanceSn as SParent


# interrupteur global (optionnel)
SURV_NOTIF_ENABLED = getattr(settings, "SURV_NOTIF_ENABLED", True)
SURV_FORMULAIRE_NAME = getattr(settings, "SURV_FORMULAIRE_NAME", "Rapportage")  # filtre sur alerts.DestinataireAlerte.formulaire


def _recipients_from_db(formulaire: str = SURV_FORMULAIRE_NAME) -> List[str]:
    """
    Récupère les emails des destinataires actifs pour le formulaire ciblé.
    -> alerts.DestinataireAlerte(formulaire='Rapportage', actif=True)
    """
    emails = list(
        DestinataireAlerte.objects
        .filter(actif=True, formulaire=formulaire)
        .values_list("email", flat=True)
    )
    # fallback paramétrable si la table est vide
    if not emails:
        emails = list(getattr(settings, "AHIS_DEFAULT_NOTIF_RECIPIENTS", []))
    # dédup basique
    return sorted(set(e for e in emails if e))


def _detail_url(parent: SParent) -> str:
    """
    Construit un lien absolu vers la fiche du foyer.
    Adapte le path à ta route réelle si besoin.
    """
    base = getattr(settings, "SITE_URL", "").rstrip("/")
    path = f"/modules/surveillance_sn/foyer/{parent.pk}/"
    return f"{base}{path}" if base else path


def notify_new_suspicion(parent: SParent) -> int:
    """
    Envoie un email lors d’une NOUVELLE suspicion (création de SParent).
    Retourne 0/1 (nb de mails envoyés selon backend).
    """
    if not SURV_NOTIF_ENABLED:
        return 0

    recipients = _recipients_from_db()
    if not recipients:
        return 0

    maladie = (parent.grp5_qmad1 or "Maladie non précisée").strip()
    region = (parent.grp3_region or "—").strip()
    dept   = (parent.grp3_departement or "—").strip()
    commune= (parent.grp3_commune or "—").strip()
    village= (parent.grp3_nom_du_village or "").strip() or (parent.grp3_lieususpicion or "—")
    d_sig  = parent.grp1_date_signalement.strftime("%d/%m/%Y") if parent.grp1_date_signalement else "—"
    d_rap  = parent.grp1_date_rapportage.strftime("%d/%m/%Y") if parent.grp1_date_rapportage else "—"
    url    = _detail_url(parent)
    kobo_id = parent.instance_id or parent.pk

    subject = f"[AHIS] Nouvelle suspicion – {maladie} – {region}/{commune}"
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "no-reply@ahis.local")

    text_body = (
        "Nouvelle suspicion enregistrée dans AHIS\n\n"
        f"Maladie      : {maladie}\n"
        f"Date signal. : {d_sig}\n"
        f"Date rapp.   : {d_rap}\n"
        f"Localisation : {village} ({commune}, {dept}, {region})\n"
        f"ID Kobo      : {kobo_id}\n\n"
        f"Consulter : {url}\n"
    )
    html_body = f"""
    <h3>Nouvelle suspicion enregistrée</h3>
    <table style="border-collapse:collapse">
      <tr><td style="padding:4px 8px"><b>Maladie</b></td><td style="padding:4px 8px">{escape(maladie)}</td></tr>
      <tr><td style="padding:4px 8px"><b>Date signalement</b></td><td style="padding:4px 8px">{escape(d_sig)}</td></tr>
      <tr><td style="padding:4px 8px"><b>Date rapportage</b></td><td style="padding:4px 8px">{escape(d_rap)}</td></tr>
      <tr><td style="padding:4px 8px"><b>Localisation</b></td>
          <td style="padding:4px 8px">{escape(village)} ({escape(commune)}, {escape(dept)}, {escape(region)})</td></tr>
      <tr><td style="padding:4px 8px"><b>ID Kobo</b></td><td style="padding:4px 8px">{escape(str(kobo_id))}</td></tr>
    </table>
    <p><a href="{escape(url)}">Ouvrir la fiche dans AHIS</a></p>
    """

    msg = EmailMultiAlternatives(subject, text_body, from_email, recipients)
    msg.attach_alternative(html_body, "text/html")
    return msg.send(fail_silently=True)
