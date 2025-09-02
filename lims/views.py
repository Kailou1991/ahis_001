# lims/views.py
from __future__ import annotations
from collections import defaultdict
from datetime import datetime
from genericpath import exists
import hashlib

from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F, Count, Min
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone as dj_timezone

from Departement.models import Departement
from Commune.models import Commune

from .services import next_code_demande
from .models import (
    Demande, Echantillon, TestCatalogue, Analyse, Equipement, PieceJointe,
    AnalyseComment,  # journal d’analyses
    DemandeEtat, DemandeEtatEntry, Rapport, user_in_groups # référentiel & journal d’états
)
from .forms import (
    DemandeForm, EchantillonFormSet, PieceJointeForm,
    SoumissionnaireQuickForm,
    AnalyseCommentForm,        # commentaire d’ANALYSE
    DemandeCommentForm,        # commentaire de DEMANDE (workflow)
)

# Décorateur d’accès par groupes
from data_initialization.decorators import group_required

User = get_user_model()

# =========================
# Groupes AHIS (libellés exacts)
# =========================
AHIS_READ = (
    "Administrateur Système",
    "Analyste",
    "Superviseur Réseau labo",
    "Superviseur technique",
)
AHIS_WRITE = (
    "Administrateur Système",
    "Réceptioniste",
    "Directeur de laboratoire",
    "Responsable Qualité",
    "Superviseur technique",
)

# =========================
# Utilitaires ÉTATS (nouveau paradigme)
# =========================

def get_etats_choices():
    """Liste (code, label) pour les filtres/menus, depuis la table référentielle."""
    return list(
        DemandeEtat.objects.order_by("ordre", "code").values_list("code", "label")
    )

def apply_etat(demande: Demande, code: str, by=None, note: str = ""):
    """
    Applique un état à la demande (met à jour current_etat + journalise).
    Remplace l’ancien usage de Demande.set_etat / Demande.etat.
    """
    etat = get_object_or_404(DemandeEtat, code=code)
    DemandeEtatEntry.objects.create(demande=demande, etat=etat, by=by, note=note)
    demande.current_etat = etat
    demande.save(update_fields=["current_etat"])
    return etat

# =========================
# APIs JSON dépendances
# =========================
@group_required(*AHIS_READ)
def api_departements_by_region(request):
    region_id = request.GET.get("region_id")
    results = []
    if region_id:
        results = list(
            Departement.objects.filter(Region_id=region_id)
            .order_by("Nom").values("id", "Nom")
        )
    return JsonResponse({"results": results})

@group_required(*AHIS_READ)
def api_communes_by_departement(request):
    dep_id = request.GET.get("departement_id")
    results = []
    if dep_id:
        results = list(
            Commune.objects.filter(DepartementID_id=dep_id)
            .order_by("Nom").values("id", "Nom")
        )
    return JsonResponse({"results": results})

@group_required(*AHIS_READ)
def api_next_code_demande(request):
    return JsonResponse({"code": next_code_demande()})

# =========================
# Liste des demandes
# =========================
@group_required(*AHIS_READ)
def demandes_list(request):
    qs = Demande.objects.select_related(
        "site_labo", "soumissionnaire", "region", "departement", "commune", "current_etat"
    )

    q = request.GET.get("q", "").strip()
    etat = request.GET.get("etat", "").strip()
    de = request.GET.get("de", "").strip()
    a  = request.GET.get("a", "").strip()

    if q:
        qs = qs.filter(
            Q(code_demande__icontains=q) |
            Q(motif__icontains=q) |
            Q(notes__icontains=q) |
            Q(soumissionnaire__nom_complet__icontains=q)
        )
    if etat:
        qs = qs.filter(current_etat__code=etat)
    if de:
        try:
            qs = qs.filter(cree_le__date__gte=datetime.fromisoformat(de).date())
        except Exception:
            pass
    if a:
        try:
            qs = qs.filter(cree_le__date__lte=datetime.fromisoformat(a).date())
        except Exception:
            pass

    demandes = Paginator(qs.order_by("-cree_le"), 25).get_page(request.GET.get("page"))
    can_create = request.user.is_superuser or request.user.groups.filter(name__in=AHIS_WRITE).exists()

    return render(request, "lims/demandes/list.html", {
        "demandes": demandes,
        "q": q, "etat": etat, "de": de, "a": a,
        "ETATS": get_etats_choices(),
        "can_create": can_create,
    })

# =========================
# Demandes à planifier (aucune analyse existante)
# =========================
@group_required(*AHIS_READ)
def demandes_a_planifier(request):
    qs = (
        Demande.objects.select_related("site_labo", "soumissionnaire", "region", "departement", "commune", "current_etat")
        .filter(Q(current_etat__code__in=["soumise", "recue"]) | Q(current_etat__isnull=True))
        .annotate(nb_analyses=Count("echantillons__analyses", distinct=True))
        .filter(nb_analyses=0)
    )

    q    = request.GET.get("q", "").strip()
    etat = request.GET.get("etat", "").strip()
    de   = request.GET.get("de", "").strip()
    a    = request.GET.get("a", "").strip()

    if q:
        qs = qs.filter(
            Q(code_demande__icontains=q) |
            Q(motif__icontains=q) |
            Q(notes__icontains=q) |
            Q(soumissionnaire__nom_complet__icontains=q)
        )
    if etat:
        qs = qs.filter(current_etat__code=etat)
    if de:
        try:
            qs = qs.filter(cree_le__date__gte=datetime.fromisoformat(de).date())
        except Exception:
            pass
    if a:
        try:
            qs = qs.filter(cree_le__date__lte=datetime.fromisoformat(a).date())
        except Exception:
            pass

    demandes = Paginator(qs.order_by("-cree_le"), 25).get_page(request.GET.get("page"))

    return render(request, "lims/analyses/planification_list.html", {
        "demandes": demandes,
        "q": q, "etat": etat, "de": de, "a": a,
        "ETATS": get_etats_choices(),
    })

# =========================
# Création / édition / suppression
# =========================
@group_required(*AHIS_WRITE)
@transaction.atomic
def demande_create(request):
    initial = {"code_demande": next_code_demande()}
    if request.method == "POST":
        form = DemandeForm(request.POST)
        formset = EchantillonFormSet(request.POST, prefix="ech")
        if form.is_valid() and formset.is_valid():
            demande = form.save()
            formset.instance = demande
            formset.save()
            # Journaliser l’état initial "soumise"
            try:
                apply_etat(demande, "soumise", by=request.user)
            except Exception:
                pass
            messages.success(request, "Demande créée avec ses échantillons.")
            return redirect("lims:vlims_demande_detail", pk=demande.pk)
    else:
        form = DemandeForm(initial=initial)
        formset = EchantillonFormSet(prefix="ech")

    return render(request, "lims/demandes/form.html", {
        "form": form, "formset": formset, "mode": "create"
    })

@group_required(*AHIS_WRITE)
@transaction.atomic
def demande_update(request, pk: int):
    demande = get_object_or_404(Demande, pk=pk)
    if request.method == "POST":
        form = DemandeForm(request.POST, instance=demande)
        formset = EchantillonFormSet(request.POST, instance=demande, prefix="ech")
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Demande mise à jour.")
            return redirect("lims:vlims_demande_detail", pk=demande.pk)
    else:
        form = DemandeForm(instance=demande)
        formset = EchantillonFormSet(instance=demande, prefix="ech")

    return render(request, "lims/demandes/form.html", {
        "form": form, "formset": formset, "mode": "update", "demande": demande
    })

@group_required(*AHIS_WRITE)
def demande_delete(request, pk: int):
    demande = get_object_or_404(Demande, pk=pk)
    if request.method == "POST":
        code = demande.code_demande
        demande.delete()
        messages.success(request, f"Demande {code} supprimée.")
        return redirect("lims:vlims_demandes_list")
    return redirect("lims:vlims_demande_detail", pk=pk)

# =========================
# Helpers: SLA & Workflow (affichage)
# =========================
def _sla_badge(a: Analyse):
    now = dj_timezone.now()
    if not a.date_echeance:
        return ("secondary", "—")
    ref = a.termine_le or now
    if ref > a.date_echeance:
        return ("danger", "En retard")
    if not a.termine_le and (a.date_echeance - now).total_seconds() <= 24 * 3600:
        return ("warning", "Échéance proche")
    return ("success", "Dans les temps")

def _compute_flags(analyses_qs, demande: Demande):
    """
    Flags de pilotage du stepper/états — version sans 'interpretation' / 'resultat_brut'.
    """
    has_analyses = analyses_qs.exists()
    any_assigned = has_analyses and analyses_qs.filter(analyste__isnull=False).exists()
    any_started  = has_analyses and (analyses_qs.filter(etat=Analyse.EN_COURS).exists()
                                     or analyses_qs.filter(debute_le__isnull=False).exists())
    all_done     = has_analyses and analyses_qs.exclude(
        etat__in=[Analyse.TERMINEE, Analyse.VALIDE_TECH, Analyse.VALIDE_BIO]
    ).count() == 0

    has_conclusion = demande.suspicion_statut in ("confirmee", "infirmee")

    # Rapport dispo ?
    from .models import Rapport
    has_report = Rapport.objects.filter(demande_id=demande.pk).exists()

    return {
        "has_analyses": has_analyses,
        "any_assigned": any_assigned,
        "any_started": any_started,
        "all_done": all_done,
        "has_conclusion": has_conclusion,
        "has_report": has_report,
    }

def _workflow_from_analyses(demande, analyses_qs):
    """
    Stepper visuel SANS champs 'resultat_brut' / 'interpretation'.
    Étapes : Soumise → Reçue → Planifiée → En cours → Analyses terminées → Conclusion (suspicion) → Rapporté
    """
    total = analyses_qs.count()
    has_analyses = total > 0

    any_started   = has_analyses and analyses_qs.filter(debute_le__isnull=False).exists()
    any_en_cours  = has_analyses and analyses_qs.filter(etat=Analyse.EN_COURS).exists()
    all_terminees = has_analyses and analyses_qs.exclude(
        etat__in=[Analyse.TERMINEE, Analyse.VALIDE_TECH, Analyse.VALIDE_BIO]
    ).count() == 0

    has_conclusion = demande.suspicion_statut in ("confirmee", "infirmee")
    is_rapportee = getattr(demande, "rapports", None) and demande.rapports.exists()

    agg = analyses_qs.aggregate(
        first_echeance = Min("date_echeance"),
        first_debut    = Min("debute_le"),
        first_termine  = Min("termine_le"),
    )

    if has_analyses:
        ts_planif = agg["first_debut"] or agg["first_echeance"] or demande.recu_le or demande.cree_le
    else:
        ts_planif = None

    ts_en_cours  = (agg["first_debut"] or ts_planif) if (any_en_cours or any_started or all_terminees or has_conclusion or is_rapportee) else None
    ts_terminees = (agg["first_termine"] or ts_en_cours) if (all_terminees or has_conclusion or is_rapportee) else None
    ts_conclu    = (demande.suspicion_le or ts_terminees) if (has_conclusion or is_rapportee) else None
    ts_rapport   = demande.rapports.aggregate(ts=Min("cree_le"))["ts"] if is_rapportee else None

    steps = [
        {"key": "soumise",    "label": "Soumise",               "done": True,                         "ts": demande.cree_le, "icon": "bi-inbox"},
        {"key": "recue",      "label": "Reçue au labo",         "done": bool(demande.recu_le),        "ts": demande.recu_le, "icon": "bi-box-arrow-in-down"},
        {"key": "planif",     "label": "Planifiée",             "done": has_analyses,                 "ts": ts_planif,       "icon": "bi-calendar-check"},
        {"key": "encours",    "label": "En cours d’analyses",   "done": (any_en_cours or any_started or all_terminees or has_conclusion or is_rapportee), "ts": ts_en_cours,  "icon": "bi-play-fill"},
        {"key": "terminees",  "label": "Analyses terminées",    "done": (all_terminees or has_conclusion or is_rapportee),                                 "ts": ts_terminees,"icon": "bi-check2-circle"},
        {"key": "conclusion", "label": "Conclusion (suspicion)","done": has_conclusion,               "ts": ts_conclu,       "icon": "bi-clipboard2-check"},
        {"key": "rapport",    "label": "Rapporté",              "done": is_rapportee,                 "ts": ts_rapport,      "icon": "bi-file-earmark-text"},
    ]

    done_count  = sum(1 for s in steps if s["done"])
    percent     = round(done_count / len(steps) * 100) if steps else 0
    current_idx = next((i for i, s in enumerate(steps) if not s["done"]), len(steps) - 1)
    current_lbl = steps[current_idx]["label"]
    return steps, percent, current_lbl


def _state_actions(demande: Demande, analyses_qs):
    """
    Construit la liste des actions “Changer l’état” basées sur les codes référentiels.
    Version nettoyée (séquentielle) sans dépendance aux bruts/interprétation.
    """
    flags = _compute_flags(analyses_qs, demande)
    curr_code = demande.current_etat.code if demande.current_etat_id else None

    def _find_etat(*codes_try):
        """Retourne l'objet DemandeEtat du premier code existant dans la liste, sinon None."""
        for c in codes_try:
            try:
                return DemandeEtat.objects.get(code=c)
            except DemandeEtat.DoesNotExist:
                continue
        return None

    actions = []

    # 1) Reçue
    et_recue = _find_etat("recue")
    if et_recue:
        enabled = not bool(demande.recu_le)
        actions.append({
            "key": et_recue.code, "label": et_recue.label,
            "enabled": (et_recue.code != curr_code) and enabled,
            "reason": None if enabled else "Déjà marquée reçue.",
        })

    # 2) Planifiée / Affectée
    et_planif = _find_etat("planifiee", "planif", "affectee")
    if et_planif:
        enabled = flags["has_analyses"]
        actions.append({
            "key": et_planif.code, "label": et_planif.label,
            "enabled": (et_planif.code != curr_code) and enabled,
            "reason": None if enabled else "Aucune analyse planifiée/affectée.",
        })

    # 3) En cours / Démarrée
    et_encours = _find_etat("analyse_demarree", "analyse_demarre", "en_cours")
    if et_encours:
        enabled = flags["any_started"]
        actions.append({
            "key": et_encours.code, "label": et_encours.label,
            "enabled": (et_encours.code != curr_code) and enabled,
            "reason": None if enabled else "Aucune analyse en cours.",
        })

    # 4) Terminées
    et_terminees = _find_etat("analyse_terminee", "analyses_terminees", "terminees")
    if et_terminees:
        enabled = flags["all_done"]
        actions.append({
            "key": et_terminees.code, "label": et_terminees.label,
            "enabled": (et_terminees.code != curr_code) and enabled,
            "reason": None if enabled else "Toutes les analyses ne sont pas terminées.",
        })

    # 5) Conclusion (suspicion)
    et_conclusion = _find_etat("conclusion", "suspicion_conclue", "conclue")
    if et_conclusion:
        enabled = flags["has_conclusion"]
        actions.append({
            "key": et_conclusion.code, "label": et_conclusion.label,
            "enabled": (et_conclusion.code != curr_code) and enabled,
            "reason": None if enabled else "Conclusion de suspicion non encore saisie.",
        })

    # 6) Rapporté
    et_rapporte = _find_etat("rapporte", "rapport_envoye", "rapport")
    if et_rapporte:
        enabled = flags["has_report"]
        actions.append({
            "key": et_rapporte.code, "label": et_rapporte.label,
            "enabled": (et_rapporte.code != curr_code) and enabled,
            "reason": None if enabled else "Aucun rapport disponible pour cette demande.",
        })

    return actions




from pathlib import Path
from django.contrib.contenttypes.models import ContentType as CT
@group_required(*AHIS_READ)
def demande_detail(request, pk: int):
    demande = get_object_or_404(
        Demande.objects.select_related(
            "site_labo", "soumissionnaire", "region", "departement", "commune", "current_etat"
        ),
        pk=pk,
    )

    # Échantillons
    echantillons = demande.echantillons.all().order_by("code_echantillon")

    # Analyses
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

    # Pièces jointes (au niveau Demande)
    ct_demande = ContentType.objects.get_for_model(Demande)
    pieces = PieceJointe.objects.filter(
        content_type=ct_demande, object_id=demande.pk
    ).order_by("-ajoute_le")

    # Stepper
    wf_steps, wf_percent, wf_current = _workflow_from_analyses(demande, analyses_qs)

    # ---------- Timeline (États + PJs Demande + Analyses + PJs Analyses + Rapports)
    def _file_icon(fname: str) -> str:
        n = (fname or "").lower()
        if n.endswith(".pdf"): return "bi-file-earmark-pdf"
        if n.endswith((".xlsx", ".xls")): return "bi-file-earmark-spreadsheet"
        if n.endswith((".csv", ".tsv")): return "bi-filetype-csv"
        if n.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")): return "bi-file-earmark-image"
        if n.endswith((".doc", ".docx")): return "bi-file-earmark-word"
        if n.endswith((".ppt", ".pptx")): return "bi-file-earmark-ppt"
        if n.endswith(".txt"): return "bi-file-earmark-text"
        return "bi-paperclip"

    now_ts = dj_timezone.now()
    events = []

    def push(title, ts=None, icon="bi-dot", subtitle=None, meta=None, **extra):
        ev = {"title": title, "ts": ts, "icon": icon, "subtitle": subtitle, "meta": meta}
        ev.update(extra)  # ex: href, file_name, file_icon
        events.append(ev)

    # 1) États historisés
    for entry in (
        DemandeEtatEntry.objects
        .filter(demande=demande)
        .select_related("etat", "by")
        .order_by("at")
    ):
        subtitle = f"par {getattr(entry.by, 'username', '—')}"
        push(f"État: {entry.etat.label}", entry.at, entry.etat.icon or "bi-flag",
             subtitle=subtitle, meta=entry.note or "")

    # 2) Pièces jointes AU NIVEAU DEMANDE (dans l'historique)
    for pj in pieces.order_by("ajoute_le"):
        fname = pj.nom_original or Path(getattr(pj.fichier, "name", "")).name
        furl  = getattr(pj.fichier, "url", None)
        if not furl:
            continue
        uploader = getattr(pj, "ajoute_par", None)
        subtitle = f"Ajoutée par {getattr(uploader, 'username', '—')}" if uploader else None
        push(
            "Pièce jointe (demande)",
            pj.ajoute_le,
            _file_icon(fname),
            subtitle=subtitle,
            meta=fname,
            href=furl,
            file_name=fname,
            file_icon=_file_icon(fname),
        )

    # 3) Analyses + PJs AU NIVEAU ANALYSE (toutes les fiches résultats)
    ct_analyse = CT.objects.get_for_model(Analyse)

    for a in analyses_qs:
        ts_planif = a.debute_le or a.date_echeance or demande.recu_le or demande.cree_le
        push(
            f"Analyse planifiée — {a.test.nom_test}",
            ts_planif,
            "bi-calendar-check",
            subtitle=f"Échantillon {a.echantillon.code_echantillon}",
        )

        if a.analyste:
            push(
                f"Affectée à {a.analyste.get_username()}",
                a.debute_le or ts_planif,
                "bi-person-check",
                meta=f"{a.test.code_test} • {a.echantillon.code_echantillon}",
            )

        if a.debute_le:
            push("Analyse démarrée", a.debute_le, "bi-play-fill", meta=a.test.code_test)
        if a.termine_le:
            push("Analyse terminée", a.termine_le, "bi-check2-circle", meta=a.test.code_test)

        # Toutes les PJs de l'analyse (fiches résultats)
        if hasattr(a, "pieces_jointes"):
            pjs = a.pieces_jointes.all().order_by("ajoute_le")
        else:
            pjs = PieceJointe.objects.filter(
                content_type=ct_analyse, object_id=a.pk
            ).order_by("ajoute_le")

        for pj in pjs:
            fname = pj.nom_original or Path(getattr(pj.fichier, "name", "")).name
            furl  = getattr(pj.fichier, "url", None)
            if not furl:
                continue
            subtitle = f"{a.test.code_test} • Éch. {a.echantillon.code_echantillon}"
            push(
                "Fiche de résultats jointe",
                pj.ajoute_le,
                _file_icon(fname),
                subtitle=subtitle,
                meta=fname,
                href=furl,
                file_name=fname,
                file_icon=_file_icon(fname),
            )

        if a.valide_tech_le:
            who = a.valide_tech_par.get_username() if a.valide_tech_par else "—"
            push("Validation technique", a.valide_tech_le, "bi-check-circle",
                 meta=f"{a.test.code_test} • par {who}")
        if a.valide_bio_le:
            who = a.valide_bio_par.get_username() if a.valide_bio_par else "—"
            push("Validation biologique", a.valide_bio_le, "bi-patch-check",
                 meta=f"{a.test.code_test} • par {who}")
        if a.annulee:
            push("Analyse annulée", a.termine_le or a.debute_le or now_ts, "bi-x-octagon",
                 meta=a.motif_annulation or a.test.code_test)

    # 4) Rapports
    from .models import Rapport
    for r in Rapport.objects.filter(demande=demande).order_by("cree_le"):
        push("Rapport généré", r.cree_le, "bi-file-earmark-text", meta=f"Version {r.version}")

    # Tri final
    events = sorted(events, key=lambda ev: ev.get("ts") or datetime.max)

    # ---------- Lignes tableau analyses (SLA + droits + lien fiche résultats)
    ana_rows = []
    for a in analyses_qs:
        perms = a.get_actions_for(request.user)
        sla_badge, sla_label = _sla_badge(a)

        # Méthode depuis choices si dispo
        try:
            methode_label = a.test.get_methode_display()
        except Exception:
            methode_label = a.test.methode

        # Dernière PJ (pour bouton)
        if hasattr(a, "pieces_jointes"):
            latest_pj = a.pieces_jointes.order_by("-ajoute_le").first()
        else:
            latest_pj = (
                PieceJointe.objects
                .filter(content_type=ct_analyse, object_id=a.pk)
                .order_by("-ajoute_le")
                .first()
            )

        result_file_url = None
        result_file_name = None
        result_file_icon = "bi-paperclip"
        if latest_pj and getattr(latest_pj, "fichier", None):
            result_file_url = getattr(latest_pj.fichier, "url", None)
            result_file_name = latest_pj.nom_original or Path(latest_pj.fichier.name).name
            result_file_icon = _file_icon(result_file_name)

        ana_rows.append({
            "id": a.pk,
            "ech": a.echantillon.code_echantillon,
            "test": a.test.nom_test,
            "code_test": a.test.code_test,
            "maladie": getattr(a.test.maladie, "Nom", None) or getattr(a.test.maladie, "nom", None) or "—",
            "section": a.test.section,
            "methode": methode_label,
            "priorite": a.get_priorite_display(),
            "analyste": a.analyste.get_username() if a.analyste else "—",
            "instrument": a.instrument.nom if a.instrument else "—",
            "debut": a.debute_le,
            "fin": a.termine_le,
            "echeance": a.date_echeance,
            "etat": a.get_etat_display(),
            "sla_badge": sla_badge,
            "sla_label": sla_label,
            "can_start": perms.get("can_start", False),
            "can_finish": perms.get("can_finish", False),
            "can_conclude": perms.get("can_conclude", False),
            "result_file_url": result_file_url,
            "result_file_name": result_file_name,
            "result_file_icon": result_file_icon,
        })

    # ---------- Compteurs & droits
    total_ech = echantillons.count()
    total_ana = analyses_qs.count()
    total_terminees = analyses_qs.filter(etat=Analyse.TERMINEE).count()
    now_for_kpi = dj_timezone.now()
    total_retard = analyses_qs.filter(
        date_echeance__isnull=False
    ).filter(
        Q(termine_le__isnull=True, date_echeance__lt=now_for_kpi) |
        Q(termine_le__isnull=False, termine_le__gt=F("date_echeance"))
    ).count()

    can_edit = (
        request.user.is_superuser
        or request.user.has_perm("lims.change_demande")
        or request.user.groups.filter(
            name__in=("Administrateur Système", "Réceptioniste", "Directeur de laboratoire", "Responsable Qualité", "Superviseur technique")
        ).exists()
    )
    can_change_state = can_edit
    state_actions = _state_actions(demande, analyses_qs)
    show_planifier = (total_ana == 0)

    # Commentaires (journal d’analyses)
    comments = (
        AnalyseComment.objects
        .filter(analyse__echantillon__demande=demande)
        .select_related("auteur", "analyse")
        .order_by("-cree_le")
    )
    comment_form = AnalyseCommentForm()

    return render(request, "lims/demandes/detail.html", {
        "demande": demande,
        "echantillons": echantillons,
        "pieces": pieces,
        "pj_form": PieceJointeForm(),

        "can_edit": can_edit,
        "can_change_state": can_change_state,
        "state_actions": state_actions,
        "show_planifier": show_planifier,

        "wf_steps": wf_steps,
        "wf_percent": wf_percent,
        "wf_current": wf_current,

        "total_ech": total_ech,
        "total_ana": total_ana,
        "total_terminees": total_terminees,
        "total_retard": total_retard,

        "events": events,
        "analyses_rows": ana_rows,

        "comment_form": comment_form,
        "comments": comments,
    })

# =========================
# Pièces jointes & États
# =========================

def _sha256_uploaded(djfile) -> str:
    """
    Calcule le SHA-256 d'un UploadedFile **sans** casser l'upload :
    on relit le flux puis on remet le curseur au début si possible.
    """
    h = hashlib.sha256()
    # tente de mémoriser la position pour .seek back
    pos = None
    fobj = getattr(djfile, "file", None)
    try:
        if fobj and hasattr(fobj, "tell"):
            pos = fobj.tell()
    except Exception:
        pos = None
    for chunk in djfile.chunks():
        h.update(chunk)
    try:
        if fobj and hasattr(fobj, "seek"):
            fobj.seek(0 if pos is None else pos)
    except Exception:
        pass
    return h.hexdigest()

@group_required(*AHIS_WRITE)
def demande_add_piece_jointe(request, pk: int):
    demande = get_object_or_404(Demande, pk=pk)
    if request.method == "POST":
        form = PieceJointeForm(request.POST, request.FILES)
        if form.is_valid():
            pj = form.save(commit=False)
            pj.content_type = ContentType.objects.get_for_model(Demande)
            pj.object_id = demande.pk
            pj.uploader = request.user

            # méta (nom, taille, checksum) si fichier présent
            up = request.FILES.get("fichier")
            if up:
                pj.nom_original = getattr(up, "name", "")[:200]
                pj.taille_octets = int(getattr(up, "size", 0) or 0)
                try:
                    pj.checksum_sha256 = _sha256_uploaded(up)
                except Exception:
                    pj.checksum_sha256 = pj.checksum_sha256 or ""

            pj.save()
            messages.success(request, "Pièce jointe ajoutée.")
        else:
            messages.error(request, "Erreur : vérifie le formulaire de pièce jointe.")
    return redirect("lims:vlims_demande_detail", pk=demande.pk)

@group_required(*AHIS_WRITE)
def demande_change_state(request, pk: int):
    """
    Remplace l’ancien changement de Demande.etat :
    on applique un code référentiel (si présent) et on journalise.
    """
    demande = get_object_or_404(Demande, pk=pk)
    nouvel_code = request.GET.get("etat")
    if not nouvel_code:
        messages.error(request, "Aucun état fourni.")
        return redirect("lims:vlims_demande_detail", pk=demande.pk)

    try:
        apply_etat(demande, nouvel_code, by=request.user)
        # side-effect : si passage à "recue", on renseigne recu_le si absent
        if nouvel_code == "recue" and not demande.recu_le:
            demande.recu_le = dj_timezone.now()
            demande.save(update_fields=["recu_le"])
        label = DemandeEtat.objects.values_list("label", flat=True).get(code=nouvel_code)
        messages.success(request, f"État changé en « {label} ».") 
    except DemandeEtat.DoesNotExist:
        messages.error(request, "État invalide.")
    return redirect("lims:vlims_demande_detail", pk=demande.pk)

# =========================
# Planification des analyses
# =========================
def _group_tests_by_section(tests):
    buckets = defaultdict(list)
    for t in tests:
        label = dict(TestCatalogue.SECTIONS).get(t.section, t.section)
        buckets[label].append(t)
    return [(sec, sorted(items, key=lambda x: (x.nom_test, x.code_test)))
            for sec, items in sorted(buckets.items(), key=lambda kv: kv[0].lower())]

@group_required(*AHIS_WRITE)
@transaction.atomic
def planifier_analyses(request, pk: int):
    demande = get_object_or_404(
        Demande.objects.select_related("site_labo", "soumissionnaire"),
        pk=pk
    )
    # Echantillons (pas de select_related('espece') ici)
    echantillons = list(
        demande.echantillons.all().order_by("pk")
    )

    grouped_tests = _group_tests_by_section(
        TestCatalogue.objects.all().order_by("section", "nom_test")
    )
    blocks = [{"e": e, "groups": grouped_tests} for e in echantillons]

    if request.method == "POST":
        priorite = request.POST.get("priorite") or "normale"
        date_echeance = request.POST.get("date_echeance") or None
        analyste_id = request.POST.get("analyste") or None
        instrument_id = request.POST.get("instrument") or None

        analyste = User.objects.filter(pk=analyste_id).first() if analyste_id else None
        instrument = Equipement.objects.filter(pk=instrument_id).first() if instrument_id else None

        created = 0
        for e in echantillons:
            for sec, tests in grouped_tests:
                for t in tests:
                    name = f"test_{e.pk}_{t.pk}"
                    if name in request.POST:
                        obj, was_created = Analyse.objects.get_or_create(
                            echantillon=e,
                            test=t,
                            defaults={
                                "etat": Analyse.NOUVELLE,
                                "priorite": priorite,
                                "date_echeance": date_echeance,
                                "analyste": analyste,
                                "instrument": instrument,
                            }
                        )
                        if was_created:
                            created += 1

        if created:
            # on peut marquer l’état “affectee” si un analyste a été choisi
            if analyste:
                try:
                    apply_etat(demande, "affectee", by=request.user)
                except Exception:
                    pass
            messages.success(request, f"{created} analyse(s) créée(s).")
        else:
            messages.info(request, "Aucune analyse créée (rien de coché ou déjà existantes).")

        return redirect("lims:vlims_demande_detail", pk=demande.pk)

    existing_by_eid = {}
    for a in Analyse.objects.filter(echantillon__in=echantillons).only("echantillon_id", "test_id"):
        existing_by_eid.setdefault(a.echantillon_id, set()).add(a.test_id)

    context = {
        "demande": demande,
        "blocks": blocks,
        "PRIORITES": Analyse.PRIORITES,
        "analystes": User.objects.all().order_by("username"),
        "instruments": Equipement.objects.filter(type="instrument").order_by("nom"),
        "existing_by_eid": existing_by_eid,
    }
    return render(request, "lims/analyses/planifier.html", context)

# =========================
# API “+ Client” (modale)
# =========================
@group_required(*AHIS_WRITE)
@require_POST
def api_soumissionnaire_create(request):
    """
    Crée rapidement un Soumissionnaire depuis la modale.
    Retour JSON: {ok: true, id: ..., label: "..."} ou {ok:false, errors:{...}}
    """
    form = SoumissionnaireQuickForm(request.POST)
    if form.is_valid():
        obj = form.save()
        label = obj.nom_complet or f"Soumissionnaire #{obj.pk}"
        return JsonResponse({"ok": True, "id": obj.pk, "label": label})
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)

# =========================
# Commentaire de DEMANDE (workflow)
# =========================
@group_required(*AHIS_WRITE)
def demande_add_comment(request, pk: int):
    """
    Ajoute un commentaire rattaché à la DEMANDE (journal du workflow de la demande),
    pas au niveau d'une analyse individuelle.
    """
    from .models import DemandeComment
    demande = get_object_or_404(Demande, pk=pk)
    if request.method == "POST":
        form = DemandeCommentForm(request.POST)
        if form.is_valid():
            c = form.save(commit=False)
            c.demande = demande
            c.auteur = request.user
            c.save()
            messages.success(request, "Commentaire ajouté.")
        else:
            messages.error(request, "Formulaire invalide.")
    return redirect("lims:vlims_demande_detail", pk=demande.pk)




###############Mes analyses##################
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q, Exists, OuterRef
from django.shortcuts import render

from .models import Demande, Echantillon, Analyse, DemandeEtat
  # si déjà présent chez toi

@login_required
def demandes_list_affectees(request):
    """
    Liste identique à 'demandes_list' mais uniquement les demandes
    qui ont au moins une Analyse affectée à l'utilisateur connecté.
    """
    # Sous-requête: existe-t-il une analyse (non annulée) de cette demande affectée à moi ?
    assigned_exists = Analyse.objects.filter(
        echantillon__demande=OuterRef("pk"),
        analyste=request.user,
        annulee=False
    )

    qs = (
        Demande.objects
        .select_related("site_labo", "soumissionnaire", "region", "departement", "commune", "current_etat")
        .annotate(has_mine=Exists(assigned_exists))
        .filter(has_mine=True)                       # <<< le filtre-clé basé sur Analyse.analyste
        .annotate(
            nb_ech=Count("echantillons", distinct=True),
            nb_ana=Count("echantillons__analyses", distinct=True),
        )
    )

    # Filtres identiques à ta vue originale
    q        = (request.GET.get("q") or "").strip()
    etat     = (request.GET.get("etat") or "").strip()
    priorite = (request.GET.get("priorite") or "").strip()
    de       = (request.GET.get("de") or "").strip()
    a        = (request.GET.get("a") or "").strip()

    if q:
        qs = qs.filter(
            Q(code_demande__icontains=q) |
            Q(motif__icontains=q) |
            Q(notes__icontains=q) |
            Q(soumissionnaire__nom_complet__icontains=q)
        )
    if etat:
        qs = qs.filter(current_etat__code=etat)
    if priorite:
        qs = qs.filter(priorite=priorite)
    if de:
        try:
            qs = qs.filter(cree_le__date__gte=datetime.fromisoformat(de).date())
        except Exception:
            pass
    if a:
        try:
            qs = qs.filter(cree_le__date__lte=datetime.fromisoformat(a).date())
        except Exception:
            pass

    page_obj = Paginator(qs.order_by("-cree_le"), 25).get_page(request.GET.get("page"))

    return render(request, "lims/demandes/mes_list.html", {
        "page_obj": page_obj,
        "q": q, "etat": etat, "priorite": priorite, "de": de, "a": a,
        "ETATS": DemandeEtat.objects.all().order_by("ordre", "code"),
        "PRIORITES": Demande.PRIORITES,
        "can_affect": user_in_groups(
            request.user,
            "Directeur de laboratoire", "Administrateur Système",
            "Responsable Qualité", "Superviseur technique"
        ),
    })
