from typing import List, Dict, Any, Tuple
from django.utils import timezone
from django.db import transaction
from kobo_integration.models import KoboForm, KoboFieldMap
from .kobo_api import fetch_schema, fetch_submissions
from .field_infer import make_field_catalog

# --- construction de catalog depuis le schéma ---
def _dtype_from_survey_type(t: str) -> str:
    if not t:
        return "string"
    t = t.strip().lower()
    if t.startswith("select_one"):
        return "select"
    if t.startswith("select_multiple"):
        # on stockera en CSV -> string
        return "string"
    if t in ("text", "note", "calculate", "string", "barcode"):
        return "string"
    if t in ("integer",):
        return "integer"
    if t in ("decimal", "number"):
        return "decimal"
    if t in ("date",):
        return "date"
    if t in ("datetime", "dateTime", "date_time"):
        return "datetime"
    if t in ("geopoint", "geotrace", "geoshape"):
        return "geo"
    if t in ("image", "photo", "picture"):
        return "image"
    if t in ("file", "audio", "video"):
        return "file"
    if t in ("acknowledge", "boolean", "yesno"):
        return "boolean"
    return "string"

def _catalog_from_schema(schema: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    """
    Construit (kobo_name, model_field, dtype) à partir du XForm 'content.survey'
    en respectant les groupes (begin_group / begin_repeat).
    """
    content = schema.get("content") or {}
    survey = content.get("survey") or []
    catalog: List[Tuple[str, str, str]] = []
    stack: List[str] = []
    used_fields: set = set()

    def sanitize(name: str) -> str:
        import re
        s = name.lower().replace("/", "_")
        s = re.sub(r"[^a-z0-9_]+", "_", s).strip("_")
        if not s:
            s = "field"
        if s[0].isdigit():
            s = f"f_{s}"
        base = s
        i = 2
        while s in used_fields:
            s = f"{base}_{i}"
            i += 1
        used_fields.add(s)
        return s

    for row in survey:
        t = (row.get("type") or "").strip().lower()
        name = row.get("name") or ""
        if t in ("begin group", "begin_group", "begin repeat", "begin_repeat"):
            if name:
                stack.append(name)
            continue
        if t in ("end group", "end_group", "end repeat", "end_repeat"):
            if stack:
                stack.pop()
            continue
        if not name:
            continue
        # chemin complet avec groupes
        parts = [*stack, name]
        key = "/".join(parts)
        dtype = _dtype_from_survey_type(t)
        model_field = sanitize(key)
        catalog.append((key, model_field, dtype))

    # métadonnées utiles si absentes
    meta_keys = [
        ("meta/instanceID", "string"),
        ("_uuid", "string"),
        ("_submission_time", "datetime"),
        ("_submitted_by", "string"),
        ("_status", "string"),
        ("_geolocation", "geo"),
    ]
    for k, d in meta_keys:
        if k not in {c[0] for c in catalog}:
            catalog.append((k, sanitize(k), d))

    return catalog

def sync_form_from_kobo(form: KoboForm, limit: int = 200) -> int:
    api_base, token, verify_ssl = form.resolve_api()
    if not token:
        raise RuntimeError("Aucun token détecté. Renseigne une Connexion Kobo (ou KOBO_TOKEN en fallback).")

    asset_uid = form.asset_uid or (form.xform_id_string if str(form.xform_id_string).startswith('a') else None)
    if not asset_uid:
        asset_uid = form.xform_id_string  # dernier recours

    # 1) Récupère schéma + submissions
    schema = {}
    submissions: List[Dict[str, Any]] = []
    try:
        schema = fetch_schema(api_base, asset_uid, token, verify=verify_ssl)
    except Exception as e:
        # garde vide si erreur
        schema = {}

    try:
        submissions = fetch_submissions(api_base, asset_uid, token, limit=limit, verify=verify_ssl)
    except Exception as e:
        submissions = []

    # 2) Construit le catalog
    if submissions:
        catalog = make_field_catalog(submissions[:50])
    elif schema:
        catalog = _catalog_from_schema(schema)
    else:
        # rien de récupérable => on échoue explicitement
        raise RuntimeError("Impossible de récupérer des données ni un schéma pour cet asset (vérifie asset_uid et permissions).")

    # 3) Persiste : caches + KoboFieldMap (upsert)
    with transaction.atomic():
        form.schema_json = schema or None
        form.sample_json = submissions[:10] or None
        form.field_catalog_json = [{"kobo_name": k, "model_field": m, "dtype": d} for k, m, d in catalog]
        form.last_synced_at = timezone.now()
        form.save(update_fields=["schema_json", "sample_json", "field_catalog_json", "last_synced_at"])

        touched = 0
        for kobo_name, model_field, dtype in catalog:
            obj, created = KoboFieldMap.objects.update_or_create(
                form=form, kobo_name=kobo_name,
                defaults={"model_field": model_field, "dtype": dtype}
            )
            if created or obj.model_field != model_field or obj.dtype != dtype:
                touched += 1

    return touched
