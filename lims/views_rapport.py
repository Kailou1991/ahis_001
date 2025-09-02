# lims/views_rapport.py
from __future__ import annotations
from collections import Counter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone as dj_tz

from .models import Demande, Analyse, Rapport, DemandeEtat
from .views import apply_etat  # utilitaire existant

# Groupes autorisés à générer un rapport
_ALLOWED_GROUPS_FOR_REPORT = ("Administrateur Système", "Directeur de laboratoire")


def _can_generate_report(user) -> bool:
    return (
        user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name__in=_ALLOWED_GROUPS_FOR_REPORT).exists()
            or user.has_perm("lims.add_rapport")
        )
    )


@login_required
@transaction.atomic
def rapport_generate(request, demande_id: int):
    """
    Génère le rapport 'ministère' (HTML ou PDF via WeasyPrint).
    - Autorisé: Admin Système ou Directeur de laboratoire
    - Nécessite que la demande soit CONCLUE (suspicion_le non nul)
    - Écrasement : supprime les anciens Rapport de la demande (et leur fichier)
    - Sert le PDF en inline (ou attachment si ?dl=1)
    """
    demande = get_object_or_404(Demande, pk=demande_id)

    # Autorisations
    if not _can_generate_report(request.user):
        messages.error(request, "Action non autorisée (réservée au Directeur ou Administrateur Système).")
        return redirect("lims:vlims_demande_detail", pk=demande.pk)

    # Doit être conclue (cohérent avec l'affichage conditionnel du bouton)
    if not demande.suspicion_le:
        messages.error(request, "La demande n'est pas encore conclue — rapport impossible.")
        return redirect("lims:vlims_demande_detail", pk=demande.pk)

    # Analyses de la demande
    analyses_qs = (
        Analyse.objects.select_related(
            "echantillon",
            "test", "test__maladie",
            "analyste", "instrument",
            "valide_tech_par", "valide_bio_par",
        )
        .filter(echantillon__demande=demande)
        .order_by("echantillon__code_echantillon", "test__code_test")
    )
    if not analyses_qs.exists():
        messages.error(request, "Aucune analyse pour cette demande — rapport impossible.")
        return redirect("lims:vlims_demande_detail", pk=demande.pk)

    # Auto-validation TECH/BIO (si non encore validées) pour les analyses TERMINÉES
    now = dj_tz.now()
    updated_tech = updated_bio = 0
    for a in analyses_qs:
        if not a.termine_le:
            continue
        if not a.valide_tech_le:
            a.valide_tech_le = now
            a.valide_tech_par = request.user
            updated_tech += 1
        if not a.valide_bio_le:
            a.valide_bio_le = now
            a.valide_bio_par = request.user
            updated_bio += 1
        try:
            if hasattr(Analyse, "VALIDE_BIO") and a.etat != Analyse.VALIDE_BIO:
                a.etat = Analyse.VALIDE_BIO
        except Exception:
            pass
        a.save()

    if updated_tech or updated_bio:
        messages.success(
            request, f"Validations appliquées — technique: {updated_tech}, biologique: {updated_bio}."
        )

    # ===== ÉCRASEMENT : supprime les anciens rapports et leur fichier PDF =====
    for old in Rapport.objects.filter(demande=demande):
        try:
            if getattr(old, "fichier_pdf", None):
                old.fichier_pdf.delete(save=False)
        except Exception:
            pass
        old.delete()

    # Re-crée un unique rapport (version figée à 1)
    rapport = Rapport.objects.create(
        demande=demande,
        version=1,
        cree_le=now,
        signe_par=request.user,
    )

    # --------- Données de rapport (modèle ministère) ---------
    # Échantillons
    echantillons = list(demande.echantillons.all().order_by("code_echantillon"))
    codes_ech = ", ".join(e.code_echantillon for e in echantillons) or "—"

    # Matrices distinctes (avec précision si 'Autre')
    matrices = []
    for e in echantillons:
        lab = e.get_matrice_display()
        if e.matrice == e.Matrices.AUTRE and e.matrice_autre:
            lab = f"{lab} ({e.matrice_autre})"
        matrices.append(lab)
    matrices_uniq = ", ".join(dict.fromkeys(matrices)) or "—"

    # Bornes de dates d'analyse
    debuts = [a.debute_le for a in analyses_qs if a.debute_le]
    fins = [a.termine_le for a in analyses_qs if a.termine_le]
    debut_min = min(debuts) if debuts else None
    fin_max = max(fins) if fins else None

    # Section dominante → Service/lieu d'exécution
    sections = [a.test.section for a in analyses_qs if a.test and a.test.section]
    section_dom = Counter(sections).most_common(1)[0][0] if sections else None
    SECTION_LABEL = {
        "PCR": "Virologie",
        "Serologie": "Sérologie",
        "Bacterio": "Bactériologie",
        "Parasito": "Parasitologie",
        "Histo": "Histopathologie",
    }
    service_lieu = SECTION_LABEL.get(section_dom, "—")

    # Client / contact
    s = demande.soumissionnaire
    client_bits = []
    if getattr(s, "nom_complet", "").strip():
        client_bits.append(s.nom_complet.strip())
    if getattr(s, "organisation", "").strip():
        client_bits.append(f"s/c {s.organisation.strip()}")
    if getattr(s, "telephone", "").strip():
        client_bits.append(f"Cel : {s.telephone.strip()}")
    if getattr(s, "email", "").strip():
        client_bits.append(f"Email : {s.email.strip()}")
    client_contact = "  ".join(client_bits) if client_bits else "—"

    # Référence/numéro du rapport (simple et stable)
    site_code = getattr(demande.site_labo, "code", "SV")
    reference_rapport = f"{now:%y}/{str(rapport.pk).zfill(4)}/{site_code}"

    # Libellé maladie (vrai nom si dispo)
    mal = None
    first = analyses_qs.first()
    if first and first.test and first.test.maladie:
        mal = (
            getattr(first.test.maladie, "Nom", None)
            or getattr(first.test.maladie, "name", None)
            or getattr(first.test.maladie, "nom", None)
        )
    # fallback : maladie déclarée sur la demande
    if not mal and demande.maladie_suspectee:
        mal = (
            getattr(demande.maladie_suspectee, "Nom", None)
            or getattr(demande.maladie_suspectee, "name", None)
            or getattr(demande.maladie_suspectee, "nom", None)
            or str(demande.maladie_suspectee)
        )
    maladie_label = mal or "la maladie suspectée"

    # Résumé "Résultats d’analyses"
    if demande.suspicion_statut == "confirmee":
        resultats_global = f"Positif à {maladie_label}"
    elif demande.suspicion_statut == "infirmee":
        resultats_global = f"Négatif à {maladie_label}"
    else:
        resultats_global = "Résultats disponibles dans le tableau et les fiches jointes."

    # Mentions particulières = commentaire de conclusion (sinon fallback numéros)
    suspicion_notes = (demande.suspicion_notes or "").strip()
   
    mentions_particulieres = (
            f"Effectif de départ : {demande.effectif_troupeau or '—'}\n"
            f"Animaux malades : {demande.nbre_animaux_malades or '—'}\n"
            f"Animaux morts : {demande.nbre_animaux_morts or '—'}"
        )

    # Contexte template
    ctx = {
        "demande": demande,
        "analyses": analyses_qs,
        "echantillons": echantillons,
        "rapport": rapport,
        "date_emission": now,
        "reference_rapport": reference_rapport,
        "client_contact": client_contact,
        "codes_ech": codes_ech,
        "matrices_uniq": matrices_uniq,
        "nb_ech": len(echantillons),
        "service_lieu": service_lieu,
        "debut_min": debut_min,
        "fin_max": fin_max,
        "resultats_global": resultats_global,
        "mentions_particulieres": mentions_particulieres,
    }

    # Journaliser 'rapporte'
    try:
        apply_etat(demande, "rapporte", by=request.user, note="Rapport généré (remplacement des versions précédentes)")
    except DemandeEtat.DoesNotExist:
        pass

    # Rendu
    fmt = (request.GET.get("format") or "html").lower()
    download = (request.GET.get("dl") in ("1", "true", "yes"))
    if fmt == "pdf":
        html = render_to_string("lims/rapports/rapport.html", ctx, request=request)
        filename = f"rapport_{demande.code_demande}.pdf".replace(" ", "_")  # stable (pas de vX)
        try:
            from weasyprint import HTML
            pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
            resp = HttpResponse(pdf_bytes, content_type="application/pdf")
            resp["Content-Disposition"] = f'{"attachment" if download else "inline"}; filename="{filename}"'
            return resp
        except Exception:
            messages.warning(request, "Génération PDF indisponible — affichage HTML du rapport.")
            return render(request, "lims/rapports/rapport.html", ctx)

    return render(request, "lims/rapports/rapport.html", ctx)
