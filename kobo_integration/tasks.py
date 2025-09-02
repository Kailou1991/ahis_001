# kobo_integration/tasks.py
from __future__ import annotations

from pathlib import Path
from datetime import timedelta
import subprocess
import sys

from celery import shared_task
from django.conf import settings


DEF_COMMENT = "# auto-added by generator\n"


def _ensure_installed(app_fullname: str) -> bool:
    """
    Ajoute l'app dans INSTALLED_APPS (settings.py) si absente.
    Retourne True si ajout effectué, False sinon.
    """
    pkg = settings.SETTINGS_MODULE.split(".")[0]  # ex: AHIS001
    settings_path = Path(settings.BASE_DIR) / pkg / "settings.py"
    txt = settings_path.read_text(encoding="utf-8")
    if f"'{app_fullname}'" in txt or f'"{app_fullname}"' in txt:
        return False
    txt += f"\n{DEF_COMMENT}INSTALLED_APPS += ['{app_fullname}']\n"
    settings_path.write_text(txt, encoding="utf-8")
    return True


def _run_manage(*args: str) -> None:
    """Exécute manage.py avec les arguments fournis (best effort, sans raise)."""
    manage_py = Path(settings.BASE_DIR) / "manage.py"
    subprocess.run(
        [sys.executable, str(manage_py), *args],
        check=False,
        cwd=str(settings.BASE_DIR),
    )


@shared_task(name="generate_module_task", ignore_result=False)
def generate_module_task(kobo_form_id: int) -> dict:
    """
    Bouton 'Générer' :
    - génère/actualise l'app à partir du mapping
    - s’assure qu’elle est dans INSTALLED_APPS
    - lance makemigrations/migrate
    - attache (best effort) droits & menu
    """
    # Imports différés pour éviter les imports circulaires
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from kobo_integration.services.generator import generate_app

    result = generate_app(kobo_form_id)
    if not isinstance(result, tuple):
        raise ValueError("generate_app() doit renvoyer un tuple.")
    if len(result) == 3:
        app_slug, model_name, logs = result
    elif len(result) == 2:
        app_slug, model_name = result
        logs = ""
    else:
        raise ValueError("generate_app() doit renvoyer (app_slug, model_name[, logs]).")

    app_full = f"generated_apps.{app_slug}"
    app_label = app_slug

    # Ajouter l'app si besoin
    _ensure_installed(app_full)

    # Migrations
    _run_manage("makemigrations", app_label)
    _run_manage("migrate", app_label, "--noinput")

    # Rattacher permissions CRUD et menu (best effort)
    try:
        from kobo_integration.models import KoboForm
        form = KoboForm.objects.get(pk=kobo_form_id)

        # Permissions CRUD -> groupes
        try:
            ct = ContentType.objects.get(app_label=app_label, model=model_name.lower())
            codes = [
                f"view_{model_name.lower()}",
                f"add_{model_name.lower()}",
                f"change_{model_name.lower()}",
                f"delete_{model_name.lower()}",
            ]
            perms = list(Permission.objects.filter(content_type=ct, codename__in=codes))
            if perms:
                for g in form.allowed_groups.all():
                    g.permissions.add(*perms)
        except Exception:
            pass

        # Ajout au menu (si core_menu existe)
        try:
            from core_menu.models import MenuItem
            mi, _ = MenuItem.objects.get_or_create(
                label=form.name,
                defaults={"url_name": f"{app_slug}:list", "app_label": app_slug},
            )
            mi.url_name = f"{app_slug}:list"
            mi.app_label = app_slug
            mi.save()
            mi.groups.set(form.allowed_groups.all())
        except Exception:
            pass
    except Exception:
        pass

    return {"app_slug": app_slug, "model_name": model_name, "logs": logs}


@shared_task(name="sync_kobo_schema_task", ignore_result=False)
def sync_kobo_schema_task(kobo_form_id: int, limit: int = 200) -> int:
    """
    Met à jour le schéma/mapping depuis Kobo.
    Si kobo_integration.services.syncer n'existe pas, fallback sur generate_app.
    """
    from kobo_integration.models import KoboForm

    try:
        from kobo_integration.services.syncer import sync_form_from_kobo
        form = KoboForm.objects.get(pk=kobo_form_id)
        return int(sync_form_from_kobo(form, limit=limit) or 0)
    except Exception:
        # Fallback simple : régénérer le module
        res = generate_module_task(kobo_form_id)
        return 1 if res else 0


@shared_task(name="sync_form_task", ignore_result=False)
def sync_form_task(kobo_form_id: int, full: bool = False, limit: int | None = None) -> dict:
    """
    Synchronise les **données** d'un formulaire.
    - full=False => delta depuis last_synced_at (avec léger overlap)
    """
    from kobo_integration.models import KoboForm
    from kobo_integration.services.runtime_sync import sync_submissions

    form = KoboForm.objects.get(pk=kobo_form_id)
    since = None
    if not full and getattr(form, "last_synced_at", None):
        since = (form.last_synced_at - timedelta(minutes=5)).replace(microsecond=0).isoformat()

    return sync_submissions(form, since=since, limit=limit)


@shared_task(name="sync_all_kobo_data_task", ignore_result=False)
def sync_all_kobo_data_task(
    use_since: bool = True, overlap_minutes: int = 5, limit: int | None = None
) -> dict:
    """
    Synchronise les données de tous les formulaires activés.
    """
    from kobo_integration.models import KoboForm
    from kobo_integration.services.runtime_sync import sync_submissions

    total = dict(created=0, updated=0, skipped=0, errors=0)
    for f in KoboForm.objects.filter(enabled=True):
        eff_since = None
        if use_since and f.last_synced_at:
            eff_since = (
                f.last_synced_at - timedelta(minutes=overlap_minutes)
            ).replace(microsecond=0).isoformat()

        res = sync_submissions(f, since=eff_since, limit=limit)
        for k in total:
            total[k] += int(res.get(k, 0))
    return total
