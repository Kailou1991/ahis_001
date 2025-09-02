# lims/views.py (version alignée au nouveau flux)
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from email.utils import formataddr
from django.utils import timezone
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, F, Count, Min
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone as dj_tz
from django.views.decorators.http import require_POST

from data_initialization.decorators import group_required
from data_initialization.emailing import send_custom_email

from Departement.models import Departement
from Commune.models import Commune
from django.http import JsonResponse

from .forms import (
    DemandeForm, EchantillonFormSet, PieceJointeForm,
    SoumissionnaireQuickForm, AnalyseCommentForm, DemandeCommentForm,
    EchantillonFormSetCreate,   # <-- import requis
    EchantillonFormSetUpdate,
)
from .models import (
    Demande, DemandeEtat, DemandeEtatEntry,
    Echantillon, Analyse, Rapport, PieceJointe, Delegation, user_in_groups,TestCatalogue,Equipement
)
from .services import next_code_demande

User = get_user_model()

# --- Groupes (lecture/écriture)
AHIS_READ = (
    "Administrateur Système",
    "Analyste",
    "Directeur de laboratoire",
    "Gestionnaire de finance",
    "Gestionnaire de stock",
    "Réceptioniste",
    "Responsable Qualité",
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
# Liste des demandes
# =========================
@group_required(*AHIS_READ)
def demandes_list(request):
    qs = (Demande.objects
          .select_related("site_labo", "soumissionnaire", "region", "departement", "commune", "current_etat")
          .annotate(nb_ech=Count("echantillons", distinct=True),
                    nb_ana=Count("echantillons__analyses", distinct=True)))

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

    return render(request, "lims/demandes/list.html", {
        "page_obj": page_obj,
        "q": q, "etat": etat, "priorite": priorite, "de": de, "a": a,
        "ETATS": DemandeEtat.objects.all().order_by("ordre", "code"),
        "PRIORITES": Demande.PRIORITES,
        "can_affect": user_in_groups(request.user, "Directeur de laboratoire", "Administrateur Système",
                                     "Responsable Qualité", "Superviseur technique"),
    })

# =========================
# SLA badge
# =========================
def _sla_badge(a: Analyse):
    now = dj_tz.now()
    if not a.date_echeance:
        return ("secondary", "—")
    ref = a.termine_le or now
    if ref > a.date_echeance:
        return ("danger", "En retard")
    if not a.termine_le and (a.date_echeance - now).total_seconds() <= 24 * 3600:
        return ("warning", "Échéance proche")
    return ("success", "Dans les temps")

# =========================
# Flags workflow (nouveau paradigme)
# =========================
def _compute_flags(demande: Demande, analyses_qs):
    has_analyses   = analyses_qs.exists()
    any_assigned   = has_analyses and analyses_qs.filter(analyste__isnull=False).exists()
    any_started    = has_analyses and (analyses_qs.filter(debute_le__isnull=False).exists()
                                       or analyses_qs.filter(etat=Analyse.EN_COURS).exists())
    all_terminees  = has_analyses and analyses_qs.exclude(
        etat__in=[Analyse.TERMINEE, Analyse.VALIDE_TECH, Analyse.VALIDE_BIO]
    ).count() == 0
    has_conclusion = demande.suspicion_statut in ("confirmee", "infirmee")
    has_report     = has_analyses and Rapport.objects.filter(demande_id=demande.id).exists()

    return {
        "has_analyses": has_analyses,
        "any_assigned": any_assigned,
        "any_started": any_started,
        "all_terminees": all_terminees,
        "has_conclusion": has_conclusion,
        "has_report": has_report,
    }

# =========================
# Stepper (7 étapes)
# =========================
def _workflow_from_demande(demande: Demande, analyses_qs):
    flags = _compute_flags(demande, analyses_qs)

    agg = analyses_qs.aggregate(
        first_echeance = Min("date_echeance"),
        first_debut    = Min("debute_le"),
        first_termine  = Min("termine_le"),
    )

    ts_planif    = (agg["first_debut"] or agg["first_echeance"] or demande.recu_le or demande.cree_le) if flags["has_analyses"] else None
    ts_en_cours  = (agg["first_debut"] or ts_planif) if (flags["any_started"] or flags["all_terminees"] or flags["has_conclusion"] or flags["has_report"]) else None
    ts_terminees = (agg["first_termine"] or ts_en_cours) if (flags["all_terminees"] or flags["has_conclusion"] or flags["has_report"]) else None
    ts_conclu    = (demande.suspicion_le or ts_terminees) if (flags["has_conclusion"] or flags["has_report"]) else None
    ts_rapport   = demande.rapports.aggregate(ts=Min("cree_le"))["ts"] if flags["has_report"] else None

    steps = [
        {"key": "soumise",    "label": "Soumise",               "done": True,                    "ts": demande.cree_le, "icon": "bi-inbox"},
        {"key": "recue",      "label": "Reçue au labo",         "done": bool(demande.recu_le),   "ts": demande.recu_le, "icon": "bi-box-arrow-in-down"},
        {"key": "planif",     "label": "Planifiée",             "done": flags["has_analyses"],   "ts": ts_planif,       "icon": "bi-calendar-check"},
        {"key": "encours",    "label": "En cours d’analyses",   "done": flags["any_started"] or flags["all_terminees"] or flags["has_conclusion"] or flags["has_report"],
                                                                  "ts": ts_en_cours,             "icon": "bi-play-fill"},
        {"key": "terminees",  "label": "Analyses terminées",    "done": flags["all_terminees"] or flags["has_conclusion"] or flags["has_report"],
                                                                  "ts": ts_terminees,            "icon": "bi-check2-circle"},
        {"key": "conclusion", "label": "Conclusion (suspicion)","done": flags["has_conclusion"], "ts": ts_conclu,       "icon": "bi-clipboard2-check"},
        {"key": "rapport",    "label": "Rapporté",              "done": flags["has_report"],     "ts": ts_rapport,      "icon": "bi-file-earmark-text"},
    ]

    done_count  = sum(1 for s in steps if s["done"])
    percent     = round(done_count / len(steps) * 100) if steps else 0
    current_idx = next((i for i, s in enumerate(steps) if not s["done"]), len(steps) - 1)
    current_lbl = steps[current_idx]["label"]
    return steps, percent, current_lbl

# =========================
# Timeline
# =========================
def _build_timeline(demande: Demande, analyses_qs):
    events = []
    def push(title, ts=None, icon="bi-dot", subtitle=None, meta=None):
        events.append({"title": title, "ts": ts, "icon": icon, "subtitle": subtitle, "meta": meta})

    # Journal des états (référentiel)
    for e in (DemandeEtatEntry.objects
              .filter(demande=demande)
              .select_related("etat", "by")
              .order_by("at", "pk")):
        who = getattr(e.by, "username", "—")
        push(f"État: {e.etat.label}", e.at, e.etat.icon or "bi-flag", subtitle=f"par {who}", meta=e.note or e.etat.code)

    # Analyses
    now = dj_tz.now()
    for a in analyses_qs:
        ts_planif = a.debute_le or a.date_echeance or demande.recu_le or demande.cree_le
        push(f"Analyse planifiée — {a.test.nom_test}", ts_planif, "bi-calendar-check",
             subtitle=f"Échantillon {a.echantillon.code_echantillon}", meta=a.test.code_test)
        if a.analyste:
            push(f"Affectée à {a.analyste.get_username()}", a.debute_le or ts_planif, "bi-person-check", meta=a.test.code_test)
        if a.debute_le:
            push("Analyse démarrée", a.debute_le, "bi-play-fill", meta=a.test.code_test)
        if a.termine_le:
            push("Analyse terminée", a.termine_le, "bi-check2-circle", meta=a.test.code_test)
        if a.valide_tech_le:
            who = a.valide_tech_par.get_username() if a.valide_tech_par else "—"
            push("Validation technique", a.valide_tech_le, "bi-check-circle", meta=f"{a.test.code_test} • par {who}")
        if a.valide_bio_le:
            who = a.valide_bio_par.get_username() if a.valide_bio_par else "—"
            push("Validation biologique", a.valide_bio_le, "bi-patch-check", meta=f"{a.test.code_test} • par {who}")
        if a.annulee:
            push("Analyse annulée", a.termine_le or a.debute_le or now, "bi-x-octagon",
                 meta=a.motif_annulation or a.test.code_test)

    # Conclusion (suspicion)
    if demande.suspicion_statut in ("confirmee", "infirmee"):
        push(f"Conclusion — {demande.get_suspicion_statut_display()}", demande.suspicion_le,
             "bi-clipboard2-check", subtitle=getattr(demande.suspicion_par, "username", "—"))

    # Rapports
    for r in Rapport.objects.filter(demande=demande).order_by("cree_le"):
        push("Rapport généré", r.cree_le, "bi-file-earmark-text", meta=f"Version {r.version}")

    return sorted(events, key=lambda ev: ev.get("ts") or datetime.max)

# =========================
# Détail d’une demande
# =========================

# views_demandes.py (ou équivalent)

from datetime import datetime
from pathlib import Path

from django.shortcuts import get_object_or_404, render
from django.db.models import Q, F
from django.utils import timezone as dj_timezone
from django.contrib.contenttypes.models import ContentType as CT

# Adapter si vos helpers ne sont pas dans .views
from .views import _workflow_from_analyses, _state_actions, _sla_badge
# Si vous avez _workflow_from_demande, il sera utilisé ci-dessous dans un try/except

from .models import (
    Demande, Echantillon, Analyse, PieceJointe,
    DemandeEtatEntry, Rapport, Delegation
)
from .forms import PieceJointeForm, AnalyseCommentForm, AnalyseComment

# Adapter ces imports selon votre projet

def _fullname_or_username(u):
    if not u:
        return "—"
    # get_full_name() peut retourner "" s'il n'est pas renseigné
    return (u.get_full_name() or u.get_username() or "—").strip()

@group_required(*AHIS_READ)
def demande_detail(request, pk: int):
    demande = get_object_or_404(
        Demande.objects.select_related(
            "site_labo", "soumissionnaire", "region", "departement", "commune",
            "current_etat", "maladie_suspectee", "espece",
        ),
        pk=pk,
    )

    echantillons = list(demande.echantillons.all().order_by("code_echantillon"))

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

    ct_demande = CT.objects.get_for_model(Demande)
    pieces = PieceJointe.objects.filter(
        content_type=ct_demande, object_id=demande.pk
    ).order_by("-ajoute_le")

    delegations = (
        Delegation.objects.filter(demande=demande)
        .select_related("utilisateur")
        .order_by("-cree_le")
    )

    # Stepper
    try:
        wf_steps, wf_percent, wf_current = _workflow_from_demande(demande, analyses_qs)
    except NameError:
        wf_steps, wf_percent, wf_current = _workflow_from_analyses(demande, analyses_qs)

    # ---------------- Timeline (avec noms complets)
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

    events = []
    def push(title, ts=None, icon="bi-dot", subtitle=None, meta=None, **extra):
        ev = {"title": title, "ts": ts, "icon": icon, "subtitle": subtitle, "meta": meta}
        ev.update(extra)
        events.append(ev)

    # 1) États historisés (affiche le nom complet)
    for entry in (
        DemandeEtatEntry.objects.filter(demande=demande)
        .select_related("etat", "by").order_by("at")
    ):
        subtitle = f"par {_fullname_or_username(entry.by)}"
        push(
            f"État: {entry.etat.label}",
            entry.at,
            entry.etat.icon or "bi-flag",
            subtitle=subtitle,
            meta=entry.note or "",
        )

    # 2) PJs au niveau Demande
    for pj in pieces.order_by("ajoute_le"):
        fname = pj.nom_original or Path(getattr(pj.fichier, "name", "")).name
        furl  = getattr(pj.fichier, "url", None)
        if not furl:
            continue
        uploader = getattr(pj, "uploader", None)
        subtitle = f"Ajoutée par {_fullname_or_username(uploader)}" if uploader else None
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

    # 3) Analyses + Fiches résultats
    ct_analyse = CT.objects.get_for_model(Analyse)
    now_ts = dj_tz.now()

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
                f"Affectée à {_fullname_or_username(a.analyste)}",
                a.debute_le or ts_planif,
                "bi-person-check",
                meta=f"{a.test.code_test} • {a.echantillon.code_echantillon}",
            )
        if a.debute_le:
            push("Analyse démarrée", a.debute_le, "bi-play-fill", meta=a.test.code_test)
        if a.termine_le:
            push("Analyse terminée", a.termine_le, "bi-check2-circle", meta=a.test.code_test)

        # Fiches résultats (PJs analyse)
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
            who = _fullname_or_username(a.valide_tech_par)
            push("Validation technique", a.valide_tech_le, "bi-check-circle",
                 meta=f"{a.test.code_test} • par {who}")
        if a.valide_bio_le:
            who = _fullname_or_username(a.valide_bio_par)
            push("Validation biologique", a.valide_bio_le, "bi-patch-check",
                 meta=f"{a.test.code_test} • par {who}")
        if a.annulee:
            push("Analyse annulée", a.termine_le or a.debute_le or now_ts, "bi-x-octagon",
                 meta=a.motif_annulation or a.test.code_test)

    # 4) Rapports
    for r in Rapport.objects.filter(demande=demande).order_by("cree_le"):
        push("Rapport généré", r.cree_le, "bi-file-earmark-text", meta=f"Version {r.version}")

    events = sorted(events, key=lambda ev: ev.get("ts") or datetime.max)

    # KPIs
    total_ech = len(echantillons)
    total_ana = analyses_qs.count()
    total_terminees = analyses_qs.filter(etat=Analyse.TERMINEE).count()
    now = dj_tz.now()
    total_retard = analyses_qs.filter(
        date_echeance__isnull=False
    ).filter(
        Q(termine_le__isnull=True, date_echeance__lt=now)
        | Q(termine_le__isnull=False, termine_le__gt=F("date_echeance"))
    ).count()

    # Lignes tableau analyses (analyste = nom complet)
    ana_rows = []
    for a in analyses_qs:
        sla_badge, sla_label = _sla_badge(a)
        maladie_label = (
            getattr(a.test.maladie, "Nom", None)
            or getattr(a.test.maladie, "name", None)
            or getattr(a.test.maladie, "nom", None)
            or "—"
        )
        try:
            methode_label = a.test.get_methode_display()
        except AttributeError:
            methode_label = a.test.methode or "—"

        perms = a.get_actions_for(request.user)

        # Dernière PJ résultat
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
            "id": a.id,
            "ech": a.echantillon.code_echantillon,
            "test": a.test.nom_test,
            "code_test": a.test.code_test,
            "maladie": maladie_label,
            "section": a.test.section,
            "methode": methode_label,
            "priorite": a.get_priorite_display(),
            "analyste": _fullname_or_username(a.analyste),   # <— NOM COMPLET
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

    # ----- Droits header
    can_edit = request.user.is_superuser or request.user.groups.filter(name__in=AHIS_WRITE).exists()
    can_change_state = can_edit
    try:
        state_actions = _state_actions(demande, analyses_qs)
    except NameError:
        state_actions = []

    # ====== Boutons « Générer rapport » (condition & permission) ======
    is_dir_or_admin = (
        request.user.is_superuser
        or request.user.groups.filter(name="Directeur de laboratoire").exists()
    )
    # Étape « Conclure l'analyse » atteinte = suspicion conclue (confirmée/infirmee)
    concluded = demande.suspicion_statut in ("confirmee", "infirmee")

    can_report = is_dir_or_admin and concluded

    show_planifier = (total_ana == 0)
    print('can_report:')
    print(can_report)
    comments = (
        AnalyseComment.objects
        .filter(analyse__echantillon__demande=demande)
        .select_related("auteur", "analyse")
        .order_by("-cree_le")
    )

    return render(request, "lims/demandes/detail.html", {
        "demande": demande,
        "echantillons": echantillons,
        "pieces": pieces,
        "delegations": delegations,

        "wf_steps": wf_steps,
        "wf_percent": wf_percent,
        "wf_current": wf_current,
        "events": events,

        "analyses_rows": ana_rows,

        "total_ech": total_ech,
        "total_ana": total_ana,
        "total_terminees": total_terminees,
        "total_retard": total_retard,

        "can_edit": can_edit,
        "can_change_state": can_change_state,
        "state_actions": state_actions,
        "show_planifier": show_planifier,

        "can_report": can_report,            # <— utilisé par le template
        "pj_form": PieceJointeForm(),
        "comment_form": AnalyseCommentForm(),
        "comments": comments,
    })
# =========================
# Ajout de pièce jointe (Demande)
# =========================
@group_required(*AHIS_WRITE)
def demande_add_piece_jointe(request, pk: int):
    demande = get_object_or_404(Demande, pk=pk)
    if request.method == "POST":
        form = PieceJointeForm(request.POST, request.FILES)
        if form.is_valid():
            pj = form.save(commit=False)
            pj.content_type = ContentType.objects.get_for_model(Demande)
            pj.object_id = demande.pk
            pj.save()
            messages.success(request, "Pièce jointe ajoutée avec succès.")
        else:
            messages.error(request, "Erreur : formulaire de pièce jointe invalide.")
    return redirect("lims:vlims_demande_detail", pk=demande.pk)

# =========================
# Commentaire DEMANDE (journal)
# =========================
@group_required(*AHIS_WRITE)
def demande_add_comment(request, pk: int):
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

# =========================
# Génération de rapport (stub)
# =========================
@group_required(*AHIS_WRITE)
def rapport_generate(request, demande_id: int):
    demande = get_object_or_404(Demande, pk=demande_id)
    r = Rapport.objects.create(demande=demande, version=1, signe_par=request.user)
    messages.success(request, "Rapport généré.")
    return redirect("lims:vlims_demande_detail", pk=demande.pk)

# =========================
# Création d’une demande
# =========================
@group_required(*AHIS_WRITE)
@transaction.atomic
def demande_create(request):
    initial = {"code_demande": next_code_demande()}
    if request.method == "POST":
        form = DemandeForm(request.POST)
        formset = EchantillonFormSetCreate(request.POST, prefix="ech")
        if form.is_valid() and formset.is_valid():
            demande = form.save()
            formset.instance = demande
            formset.save()
            # ... (journalisation, messages, redirect)
            return redirect("lims:vlims_demande_detail", pk=demande.pk)
    else:
        form = DemandeForm(initial=initial)
        formset = EchantillonFormSetCreate(prefix="ech")

    return render(request, "lims/demandes/form.html", {
        "mode": "create",
        "form": form,
        "formset": formset,
        "return_url": reverse("lims:vlims_demandes_list"),
        "api_next_code_url": reverse("lims:api_next_code_demande"),
        "api_deps_url":     reverse("lims:api_departements_by_region"),
        "api_com_url":      reverse("lims:api_communes_by_departement"),
        "api_client_url":   reverse("lims:api_soumissionnaire_create"),
    })


@group_required(*AHIS_WRITE)
@transaction.atomic
def demande_update(request, pk: int):
    demande = get_object_or_404(Demande, pk=pk)
    if request.method == "POST":
        form = DemandeForm(request.POST, instance=demande)
        formset = EchantillonFormSetUpdate(request.POST, instance=demande, prefix="ech")
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, "Demande mise à jour.")
            return redirect("lims:vlims_demande_detail", pk=demande.pk)
    else:
        form = DemandeForm(instance=demande)
        formset = EchantillonFormSetUpdate(instance=demande, prefix="ech")

    return render(request, "lims/demandes/form.html", {
        "mode": "update",
        "form": form,
        "formset": formset,
        "return_url": reverse("lims:vlims_demande_detail", args=[demande.pk]),
        "api_next_code_url": reverse("lims:api_next_code_demande"),
        "api_deps_url":     reverse("lims:api_departements_by_region"),
        "api_com_url":      reverse("lims:api_communes_by_departement"),
        "api_client_url":   reverse("lims:api_soumissionnaire_create"),
    })

@group_required(*AHIS_WRITE)
def demande_delete(request, pk: int):
    """
    Suppression autorisée uniquement si AUCUNE analyse liée n'a démarré.
    - On considère "démarré" si debute_le non nul OU état en cours/terminé/validé.
    - Si une analyse a démarré, on bloque et on affiche un message d’erreur.
    """
    demande = get_object_or_404(Demande, pk=pk)

    analyses_qs = Analyse.objects.filter(echantillon__demande=demande)

    # Une analyse est considérée "démarrée" si:
    # - debute_le est renseigné, ou
    # - son état est EN_COURS / TERMINEE / VALIDE_TECH / VALIDE_BIO
    started_exists = analyses_qs.filter(
        Q(debute_le__isnull=False) |
        Q(etat__in=[
            Analyse.EN_COURS,
            Analyse.TERMINEE,
            Analyse.VALIDE_TECH,
            Analyse.VALIDE_BIO,
        ])
    ).exists()

    if started_exists:
        messages.error(
            request,
            "Impossible de supprimer la demande : au moins une analyse a déjà démarré."
        )
        return redirect("lims:vlims_demande_detail", pk=demande.pk)

    code = demande.code_demande
    demande.delete()
    messages.success(request, f"Demande {code} supprimée.")
    return redirect("lims:vlims_demandes_list")

# =========================
# APIs JSON
# =========================
@group_required(*AHIS_WRITE)
def api_next_code_demande(request):
    return JsonResponse({"code": next_code_demande()})

@group_required(*AHIS_READ)
def api_departements_by_region(request):
    region_id = request.GET.get("region_id")
    results = []
    if region_id:
        results = list(
            Departement.objects.filter(Region_id=region_id)
            .order_by("Nom").annotate(nom=F("Nom")).values("id", "nom")
        )
    return JsonResponse({"results": results})

@group_required(*AHIS_READ)
def api_communes_by_departement(request):
    dep_id = request.GET.get("departement_id")
    results = []
    if dep_id:
        results = list(
            Commune.objects.filter(DepartementID_id=dep_id)
            .order_by("Nom").annotate(nom=F("Nom")).values("id", "nom")
        )
    return JsonResponse({"results": results})

@group_required(*AHIS_WRITE)
@require_POST
def api_soumissionnaire_create(request):
    form = SoumissionnaireQuickForm(request.POST)
    if form.is_valid():
        obj = form.save()
        return JsonResponse({"ok": True, "id": obj.pk, "label": (obj.nom_complet or f"Soumissionnaire #{obj.pk}")})
    return JsonResponse({"ok": False, "errors": form.errors}, status=400)

# =========================
# Affectation / Réaffectation d’analyses
# =========================
def _can_affect(user) -> bool:
    return user_in_groups(user, "Directeur de laboratoire", "Administrateur Système",
                          "Responsable Qualité", "Superviseur technique")

@group_required(*AHIS_WRITE)
@transaction.atomic
def demande_affecter(request, pk: int):
    demande = get_object_or_404(Demande.objects.select_related("site_labo", "soumissionnaire"), pk=pk)
    if not _can_affect(request.user):
        messages.error(request, "Vous n’êtes pas autorisé à affecter des tests.")
        return redirect("lims:vlims_demande_detail", pk=demande.pk)

    if getattr(demande, "maladie_suspectee_id", None):
        suggested_tests = TestCatalogue.objects.filter(maladie_id=demande.maladie_suspectee_id).order_by("section", "code_test")
    else:
        suggested_tests = TestCatalogue.objects.all().order_by("section", "code_test")

    eligible_analystes = User.objects.filter(Q(is_superuser=True) | Q(groups__name__in=["Analyste"]))\
                                     .distinct().order_by("username")
    instruments = Equipement.objects.filter(type="instrument").order_by("nom")

    if request.method == "POST":
        analyste_id   = request.POST.get("analyste")
        sel_test_ids  = request.POST.getlist("tests")
        priorite      = request.POST.get("priorite") or "normale"
        date_echeance = request.POST.get("date_echeance") or None
        instrument_id = request.POST.get("instrument") or None

        if not analyste_id:
            messages.error(request, "Veuillez sélectionner un analyste.")
            return redirect(request.path)

        analyste  = get_object_or_404(eligible_analystes, pk=analyste_id)
        instrument = instruments.filter(pk=instrument_id).first() if instrument_id else None
        if not sel_test_ids:
            messages.warning(request, "Aucun test sélectionné.")
            return redirect(request.path)

        tests_qs = TestCatalogue.objects.filter(pk__in=sel_test_ids)

        created_count = newly_assigned_count = reassigned_count = unchanged_count = 0
        reaff_by_old_user = defaultdict(list)
        assigned_for_new = []

        for e in demande.echantillons.all():
            for t in tests_qs:
                obj, created = Analyse.objects.get_or_create(
                    echantillon=e, test=t,
                    defaults={
                        "analyste": analyste, "priorite": priorite,
                        "date_echeance": date_echeance, "instrument": instrument,
                        "etat": Analyse.NOUVELLE, "debute_le": None, "termine_le": None,
                    },
                )
                if created:
                    created_count += 1
                    assigned_for_new.append((e.code_echantillon, t.code_test, t.nom_test, t.section, False))
                    continue

                if obj.analyste_id is None:
                    obj.analyste = analyste
                    obj.priorite = priorite
                    obj.date_echeance = date_echeance
                    obj.instrument = instrument
                    obj.save(update_fields=["analyste", "priorite", "date_echeance", "instrument"])
                    newly_assigned_count += 1
                    assigned_for_new.append((e.code_echantillon, t.code_test, t.nom_test, t.section, False))
                elif obj.analyste_id == analyste.id:
                    unchanged_count += 1
                else:
                    old_user = obj.analyste
                    obj.analyste = analyste
                    obj.etat = Analyse.NOUVELLE
                    obj.debute_le = None
                    obj.termine_le = None
                    obj.priorite = priorite
                    obj.date_echeance = date_echeance
                    obj.instrument = instrument
                    obj.save(update_fields=["analyste", "etat", "debute_le", "termine_le", "priorite", "date_echeance", "instrument"])
                    reassigned_count += 1
                    reaff_by_old_user[old_user].append((e.code_echantillon, t.code_test, t.nom_test, t.section))
                    assigned_for_new.append((e.code_echantillon, t.code_test, t.nom_test, t.section, True))

        if reassigned_count:
            etat_reaff = DemandeEtat.objects.filter(code="reaffectee").first()
            if etat_reaff:
                DemandeEtatEntry.objects.create(
                    demande=demande, etat=etat_reaff, by=request.user,
                    note=f"Réaffectation vers {analyste.get_full_name() or analyste.username}"
                )
                demande.current_etat = etat_reaff
                demande.save(update_fields=["current_etat"])

        # emails (nouvel analyste / anciens)
        def _from_email():
            return formataddr((getattr(settings, "DEFAULT_FROM_NAME", "Notification AHIS"),
                               getattr(settings, "DEFAULT_FROM_EMAIL", settings.EMAIL_HOST_USER)))
        demande_url = request.build_absolute_uri(reverse("lims:vlims_demande_detail", args=[demande.pk]))
        site_txt = str(demande.site_labo) if demande.site_labo_id else "—"
        due_txt = date_echeance or "—"
        instrument_txt = instrument.nom if instrument else "—"
        samples_count = demande.echantillons.count()

        if (created_count + newly_assigned_count + reassigned_count) > 0 and getattr(analyste, "email", ""):
            lines = []
            for ech_code, code_test, nom_test, section, was_reaff in assigned_for_new:
                badge = " (réaffectée)" if was_reaff else ""
                lines.append(f"- [{section}] {code_test} — {nom_test} / {ech_code}{badge}")
            tests_list = "\n".join(lines) if lines else "—"
            subject = f"[AHIS/LIMS] Demande {demande.code_demande} — analyses affectées"
            body = (
                f"Bonjour {analyste.get_full_name() or analyste.username},\n\n"
                f"Des analyses vous ont été affectées pour la demande {demande.code_demande}.\n\n"
                f"• Site labo : {site_txt}\n"
                f"• Priorité : {priorite}\n"
                f"• Échéance : {due_txt}\n"
                f"• Instrument : {instrument_txt}\n"
                f"• Nombre d’échantillons : {samples_count}\n\n"
                f"Analyses :\n{tests_list}\n\n"
                f"Accéder à la demande : {demande_url}\n\n— AHIS/LIMS"
            )
            try:
                send_custom_email(
                    EMAIL_HOST=settings.EMAIL_HOST,
                    EMAIL_PORT=settings.EMAIL_PORT,
                    EMAIL_USE_SSL=getattr(settings, "EMAIL_USE_SSL", False),
                    EMAIL_HOST_USER=settings.EMAIL_HOST_USER,
                    EMAIL_HOST_PASSWORD=settings.EMAIL_HOST_PASSWORD,
                    subject=subject, body=body, to=[analyste.email], from_email=_from_email()
                )
                messages.success(request, f"Notification envoyée à {analyste.email}.")
            except Exception as e:
                messages.warning(request, f"Notification (nouvel analyste) non envoyée : {e}")

        if reassigned_count and reaff_by_old_user:
            for old_user, items in reaff_by_old_user.items():
                if not getattr(old_user, "email", ""):
                    continue
                lines = [f"- [{section}] {code_test} — {nom_test} / {ech_code}"
                         for (ech_code, code_test, nom_test, section) in items]
                tests_list = "\n".join(lines) if lines else "—"
                subject = f"[AHIS/LIMS] Demande {demande.code_demande} — réaffectation"
                body = (
                    f"Bonjour {old_user.get_full_name() or old_user.username},\n\n"
                    f"Vous êtes déchargé(e) de certaines analyses sur la demande {demande.code_demande}.\n\n"
                    f"Analyses réaffectées :\n{tests_list}\n\n— AHIS/LIMS"
                )
                try:
                    send_custom_email(
                        EMAIL_HOST=settings.EMAIL_HOST,
                        EMAIL_PORT=settings.EMAIL_PORT,
                        EMAIL_USE_SSL=getattr(settings, "EMAIL_USE_SSL", False),
                        EMAIL_HOST_USER=settings.EMAIL_HOST_USER,
                        EMAIL_HOST_PASSWORD=settings.EMAIL_HOST_PASSWORD,
                        subject=subject, body=body, to=[old_user.email], from_email=_from_email()
                    )
                except Exception as e:
                    messages.warning(request, f"Notification (ancien analyste) non envoyée à {old_user.email} : {e}")

        parts = []
        if created_count: parts.append(f"{created_count} analyse(s) créée(s)")
        if newly_assigned_count: parts.append(f"{newly_assigned_count} affectée(s)")
        if reassigned_count: parts.append(f"{reassigned_count} réaffectée(s)")
        if unchanged_count and not (created_count or newly_assigned_count or reassigned_count):
            parts.append("Aucune modification")
        msg = " ; ".join(parts) if parts else "Aucune modification."
        (messages.success if (created_count or newly_assigned_count or reassigned_count) else messages.info)(request, msg)

        return redirect("lims:vlims_demande_detail", pk=demande.pk)

    return render(request, "lims/demandes/affecter_demande.html", {
        "demande": demande,
        "suggested_tests": suggested_tests,
        "eligible_analystes": eligible_analystes,
        "instruments": instruments,
    })
