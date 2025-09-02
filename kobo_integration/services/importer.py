# kobo_integration/services/importer.py
from importlib import import_module
from datetime import datetime
from django.apps import apps
from django.db import transaction
from django.utils.timezone import make_aware, is_naive

from kobo_integration.models import KoboForm, KoboFieldMap

def _load_parser(parser_path: str):
    """
    parser_path: "generated_apps.<slug>.parser:parse_payload"
    """
    mod, func = parser_path.split(":")
    module = import_module(mod)
    return getattr(module, func)

def _get_model_for_app(app_label: str):
    """
    Retourne l’unique modèle de l’app générée (app_label = slug)
    """
    appcfg = apps.get_app_config(app_label)
    models = list(appcfg.get_models())
    if not models:
        raise RuntimeError(f"Aucun modèle trouvé pour l’app '{app_label}'")
    if len(models) > 1:
        # Si un jour tu génères plusieurs modèles, adapte ici.
        raise RuntimeError(f"Plus d’un modèle trouvé dans '{app_label}'.")
    return models[0]

def _to_aware(dt):
    if not dt:
        return None
    if isinstance(dt, str):
        s = dt.replace(" ", "T")
        try:
            dt = datetime.fromisoformat(s)
        except Exception:
            return None
    if is_naive(dt):
        return make_aware(dt)
    return dt

@transaction.atomic
def upsert_one(form: KoboForm, payload: dict) -> tuple[bool, str]:
    """
    Insère/Maj UNE soumission.
    Retourne (created, instance_id)
    """
    if not form.parser_path:
        raise RuntimeError("parser_path manquant sur le KoboForm")

    parser = _load_parser(form.parser_path)
    maps = list(KoboFieldMap.objects.filter(form=form).order_by("kobo_name"))
    parsed = parser(payload, maps)

    instance_id = payload.get("meta/instanceID") or payload.get("_uuid")
    if not instance_id:
        raise RuntimeError("instance_id introuvable dans le payload")

    Model = _get_model_for_app(form.slug)

    defaults = {
        "raw_json": payload,
        "xform_id_string": payload.get("_xform_id_string"),
        "submission_time": _to_aware(payload.get("_submission_time")),
        "submitted_by": payload.get("_submitted_by"),
        "status": payload.get("_status"),
        "geojson": payload.get("_geolocation"),
        **parsed,
    }

    obj, created = Model.objects.get_or_create(instance_id=instance_id, defaults=defaults)

    if not created:
        changed = False
        # champs business (du mapping)
        for k, v in parsed.items():
            if getattr(obj, k, None) != v:
                setattr(obj, k, v); changed = True
        # champs méta
        meta_updates = {
            "raw_json": payload,
            "xform_id_string": payload.get("_xform_id_string"),
            "submission_time": _to_aware(payload.get("_submission_time")),
            "submitted_by": payload.get("_submitted_by"),
            "status": payload.get("_status"),
            "geojson": payload.get("_geolocation"),
        }
        for k, v in meta_updates.items():
            if getattr(obj, k, None) != v:
                setattr(obj, k, v); changed = True

        if changed:
            obj.save()

    return created, instance_id

def backfill_from_db(form_slug: str) -> int:
    """
    Re-parcourt toutes les lignes de l’app générée pour remplir/mettre à jour
    les colonnes à partir de raw_json + mapping.
    Retourne le nombre de lignes modifiées.
    """
    form = KoboForm.objects.get(slug=form_slug)
    parser = _load_parser(form.parser_path)
    maps = list(KoboFieldMap.objects.filter(form=form).order_by("kobo_name"))
    Model = _get_model_for_app(form.slug)

    count = 0
    for obj in Model.objects.all():
        payload = obj.raw_json or {}
        parsed = parser(payload, maps)

        changed = False
        for k, v in parsed.items():
            if getattr(obj, k, None) != v:
                setattr(obj, k, v); changed = True

        # on peut aussi re-synchroniser quelques méta si besoin
        # (utile si tu as enrichi raw_json après coup)
        meta_updates = {
            "xform_id_string": payload.get("_xform_id_string"),
            "submission_time": _to_aware(payload.get("_submission_time")),
            "submitted_by": payload.get("_submitted_by"),
            "status": payload.get("_status"),
            "geojson": payload.get("_geolocation"),
        }
        for k, v in meta_updates.items():
            if getattr(obj, k, None) != v:
                setattr(obj, k, v); changed = True

        if changed:
            obj.save(); count += 1

    return count
