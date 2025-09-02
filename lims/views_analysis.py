# lims/views_analysis.py
from __future__ import annotations

import hashlib
from email.utils import formataddr

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from data_initialization.emailing import send_custom_email
from .forms import AnalyseConcludeForm
from .models import Analyse, PieceJointe

# ---------- Email helpers (identiques à avant) ----------
def _sender_display() -> str:
    name = getattr(settings, "DEFAULT_FROM_NAME", "Notification AHIS")
    addr = getattr(settings, "DEFAULT_FROM_EMAIL", getattr(settings, "EMAIL_HOST_USER", None))
    return formataddr((name, addr))

def _group_emails(group_name: str):
    try:
        g = Group.objects.get(name=group_name)
    except Group.DoesNotExist:
        return []
    return [u.email for u in g.user_set.all() if u.email]

def _director_emails(site=None):
    return _group_emails("Directeur de laboratoire")

def _send_mail(subject: str, body: str, to: list[str], html_body: str | None = None):
    if not to:
        return 0
    return send_custom_email(
        EMAIL_HOST=settings.EMAIL_HOST,
        EMAIL_PORT=settings.EMAIL_PORT,
        EMAIL_USE_SSL=getattr(settings, "EMAIL_USE_SSL", False),
        EMAIL_HOST_USER=settings.EMAIL_HOST_USER,
        EMAIL_HOST_PASSWORD=settings.EMAIL_HOST_PASSWORD,
        subject=subject,
        body=body,
        to=to,
        from_email=_sender_display(),
        html_body=html_body,
        timeout=30,
        fail_silently=False,
    )

# ---------- utils PJ ----------
def _sha256(b: bytes) -> str:
    h = hashlib.sha256(); h.update(b); return h.hexdigest()

def _attach(analyse: Analyse, uploaded_file, user, type_hint: str = "resultat"):
    content = uploaded_file.read()
    checksum = _sha256(content)
    ext = (getattr(uploaded_file, "name", "").split(".")[-1] or "").lower()
    pj_type = {
        "pdf": "result_pdf",
        "csv": "result_csv",
        "tsv": "result_csv",
        "xlsx": "result_xlsx",
        "xls": "result_xlsx",
        "txt": "result_txt",
    }.get(ext, type_hint)

    pj = PieceJointe(
        content_object=analyse,
        type=pj_type,
        nom_original=getattr(uploaded_file, "name", "")[:200],
        taille_octets=len(content),
        checksum_sha256=checksum,
        uploader=user,
    )
    fname = f"results/{analyse.pk}_{checksum[:10]}.{ext or 'bin'}"
    pj.fichier.save(fname, ContentFile(content), save=True)
    return pj

# ---------- Démarrer ----------
@require_http_methods(["POST"])
@transaction.atomic
def analyse_start(request, pk: int):
    analyse = get_object_or_404(
        Analyse.objects.select_related("echantillon", "echantillon__demande", "test", "analyste"), pk=pk
    )
    if not analyse.get_actions_for(request.user).get("can_start", False):
        messages.error(request, "Action non autorisée.")
        return redirect("lims:vlims_demande_detail", pk=analyse.demande.pk)

    analyse.debute_le = timezone.now()
    analyse.etat = Analyse.EN_COURS
    analyse.save(update_fields=["debute_le", "etat"])
    analyse.comments.create(auteur=request.user, etape="demarrage", texte="Analyse démarrée.")
    try:
        analyse.demande.set_etat("analyse_demarre", by=request.user, note=f"Analyse {analyse.id} démarrée")
    except Exception:
        pass
    messages.success(request, "Analyse démarrée.")
    return redirect("lims:vlims_demande_detail", pk=analyse.demande.pk)

# ---------- Terminer ----------
@require_http_methods(["POST"])
@transaction.atomic
def analyse_finish(request, pk: int):
    analyse = get_object_or_404(
        Analyse.objects.select_related("echantillon", "echantillon__demande", "test", "analyste"), pk=pk
    )
    if not analyse.get_actions_for(request.user).get("can_finish", False):
        messages.error(request, "Action non autorisée.")
        return redirect("lims:vlims_demande_detail", pk=analyse.demande.pk)

    if not analyse.debute_le:
        analyse.debute_le = timezone.now()
    analyse.termine_le = timezone.now()
    analyse.etat = Analyse.TERMINEE
    analyse.save(update_fields=["debute_le", "termine_le", "etat"])
    analyse.comments.create(auteur=request.user, etape="terminaison", texte="Analyse terminée.")
    try:
        analyse.demande.set_etat("analyse_terminee", by=request.user, note=f"Analyse {analyse.id} terminée")
    except Exception:
        pass
    messages.success(request, "Analyse terminée. Vous pouvez maintenant conclure la suspicion.")
    return redirect("lims:analyse_conclude", pk=analyse.pk)

# ---------- Conclure (suspicion + PJ) ----------
@require_http_methods(["GET", "POST"])
@transaction.atomic
def analyse_conclude(request, pk: int):
    analyse = get_object_or_404(
        Analyse.objects.select_related(
            "echantillon", "echantillon__demande", "echantillon__demande__site_labo", "test", "analyste"
        ),
        pk=pk,
    )

    if not analyse.get_actions_for(request.user).get("can_conclude", False):
        messages.error(request, "Vous n’êtes pas autorisé à conclure cette analyse.")
        return redirect("lims:vlims_demande_detail", pk=analyse.demande.pk)

    dmd = analyse.demande

    if request.method == "GET":
        form = AnalyseConcludeForm(initial={
            "suspicion_statut": dmd.suspicion_statut,
            "suspicion_notes": dmd.suspicion_notes,
        })
        return render(request, "lims/analyses/conclude.html", {"analyse": analyse, "form": form})

    # POST
    form = AnalyseConcludeForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Veuillez corriger les erreurs.")
        return render(request, "lims/analyses/conclude.html", {"analyse": analyse, "form": form})

    # 1) Met à jour la suspicion sur la Demande
    dmd.suspicion_statut = form.cleaned_data["suspicion_statut"]
    dmd.suspicion_notes = form.cleaned_data.get("suspicion_notes", "")
    dmd.suspicion_par = request.user
    dmd.suspicion_le = timezone.now()
    dmd.save(update_fields=["suspicion_statut", "suspicion_notes", "suspicion_par", "suspicion_le"])

    # 2) PJ (facultatif)
    f = request.FILES.get("result_file")
    if f:
        _attach(analyse, f, request.user, type_hint="result_file")
        analyse.comments.create(auteur=request.user, etape="resultat", texte="Fiche de résultats jointe.")

    # 3) Journal + notification (optionnel)
    analyse.comments.create(auteur=request.user, etape="validation_bio", texte="Suspicion conclue via l'analyse.")

    subject = f"[AHIS/LIMS] Conclusion — {dmd.code_demande}"
    d_url = request.build_absolute_uri(reverse("lims:vlims_demande_detail", args=[dmd.pk]))
    _send_mail(
        subject=subject,
        body=(f" Bonjour les résultats sont saisis pour la demande : {dmd.code_demande} ({dmd.get_suspicion_statut_display()}).\n{d_url}"),
        to=_director_emails(dmd.site_labo),
        html_body=f"<p>Bonjour les résultats sont saisis pour la demande : {dmd.code_demande} sont disponibles : <b>{dmd.get_suspicion_statut_display()}</b></p><p><a href='{d_url}'>Ouvrir</a></p>",
    )

    messages.success(request, "Conclusion enregistrée.")
    return redirect("lims:vlims_demande_detail", pk=dmd.pk)
