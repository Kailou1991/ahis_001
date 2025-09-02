# kobo_integration/services/runtime_sync.py
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.apps import apps
from django.db import models, transaction
from django.db.utils import DataError
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from kobo_integration.models import KoboForm, KoboFieldMap


# -------------------------- utilitaires bas niveau --------------------------
def _trim_to_db_limits(values: dict, fields: Dict[str, models.Field]) -> dict:
    """
    Tronque les chaînes selon max_length pour CharField,
    sinon à 255 (utile si la colonne DB est restée en VARCHAR(255)).
    """
    out = {}
    for k, v in values.items():
        f = fields.get(k)
        if isinstance(v, str):
            ml = getattr(f, "max_length", None) if f else None
            out[k] = v[:ml] if ml else v[:255]
        else:
            out[k] = v
    return out


def _model_name_from_slug(slug: str) -> str:
    parts = [p for p in re.split(r"[^a-z0-9]+", slug.lower()) if p]
    return "".join(p.capitalize() for p in parts)


def _fields_dict(Model) -> Dict[str, models.Field]:
    out: Dict[str, models.Field] = {}
    for f in Model._meta.get_fields():
        # champs concrets uniquement (ForeignKey compris)
        if getattr(f, "concrete", False) and hasattr(f, "attname"):
            out[f.name] = f
    return out


def _flat(v: Any) -> Any:
    if isinstance(v, (str, int, float)) or v is None:
        return v
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)


def _to_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"1", "true", "yes", "y", "oui"}:
        return True
    if s in {"0", "false", "no", "n", "non"}:
        return False
    return None


def _make_aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def _fit_to_field(field: models.Field, value: Any) -> Any:
    """Applique un tronquage pour CharField (max_length)."""
    if value is None:
        return None
    if isinstance(field, models.CharField):
        ml = getattr(field, "max_length", None)
        if ml and isinstance(value, str) and len(value) > ml:
            return value[:ml]
    return value


def _coerce(field: models.Field, value: Any):
    """Convertit value au type du field, en restant permissif."""
    if value is None:
        return None

    # JSON
    if isinstance(field, models.JSONField):
        if isinstance(value, (list, dict)):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except Exception:
                return value
        return value

    # DateTime (aware)
    if isinstance(field, models.DateTimeField):
        dt: Optional[datetime] = None
        if isinstance(value, datetime):
            dt = value
        elif isinstance(value, str):
            dt = parse_datetime(value)
            if dt is None:
                try:
                    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except Exception:
                    dt = None
        return _make_aware(dt)

    # Date (pas DateTime)
    if isinstance(field, models.DateField) and not isinstance(field, models.DateTimeField):
        if isinstance(value, str):
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    return datetime.strptime(value, fmt).date()
                except Exception:
                    pass
            try:
                return datetime.fromisoformat(value).date()
            except Exception:
                return None
        return value

    # Numériques
    if isinstance(field, models.IntegerField):
        try:
            return int(str(value)) if value != "" else None
        except Exception:
            return None

    if isinstance(field, models.FloatField):
        try:
            return float(str(value)) if value != "" else None
        except Exception:
            return None

    if isinstance(field, models.DecimalField):
        from decimal import Decimal
        try:
            return Decimal(str(value)) if value != "" else None
        except Exception:
            return None

    # Booléen
    if isinstance(field, models.BooleanField):
        return _to_bool(value)

    # Char/Text -> string + ajuste si CharField
    return _fit_to_field(field, str(value))


def _canon(name: str) -> str:
    """Nom canonique (snake_case simple, sûr pour attributs)."""
    s = (name or "").replace("/", "_")
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"__+", "_", s).strip("_").lower()
    if not s or not re.match(r"[a-z_]", s[0]):
        s = "f_" + (s or "field")
    return s


SYSTEM_PARENT_FIELDS = {
    # champs système du parent
    "id",
    "instance_id",
    "xform_id_string",
    "submission_time",
    "submitted_by",
    "status",
    "geojson",
    "raw_json",
    "created_at",
    "updated_at",
}


# -------------------------- mapping valeurs parent --------------------------
def _parent_values(form: KoboForm, row: Dict[str, Any], Parent) -> Dict[str, Any]:
    fields = _fields_dict(Parent)
    maps = list(
        KoboFieldMap.objects.filter(form=form).values("kobo_name", "model_field", "dtype")
    )

    # 1) mapping explicite (hors repeats)
    #    -> on saute tout champ dont le prefix appartient à un repeat
    repeat_prefixes: set[str] = set(
        (m["kobo_name"] or "").split("/", 1)[0]
        for m in maps
        if (m.get("dtype") or "").strip().lower() == "repeat"
    )

    vals: Dict[str, Any] = {}
    for m in maps:
        kn = (m["kobo_name"] or "").strip()
        mn = (m["model_field"] or "").strip()
        if not mn or mn not in fields:
            continue
        if "/" in kn and kn.split("/", 1)[0] in repeat_prefixes:
            continue

        v = row.get(kn)
        if v is None and "/" in kn:
            v = row.get(kn.replace("/", "-")) or row.get(kn.split("/", 1)[1])
        v = _coerce(fields[mn], _flat(v))
        vals[mn] = v

    # 2) champs système
    if "xform_id_string" in fields and "_xform_id_string" in row:
        vals["xform_id_string"] = _coerce(fields["xform_id_string"], row["_xform_id_string"])
    if "submission_time" in fields and ("_submission_time" in row or "submission_time" in row):
        vals["submission_time"] = _coerce(
            fields["submission_time"], row.get("_submission_time") or row.get("submission_time")
        )
    if "submitted_by" in fields and ("_submitted_by" in row or "submitted_by" in row):
        vals["submitted_by"] = _coerce(
            fields["submitted_by"], row.get("_submitted_by") or row.get("submitted_by")
        )
    if "status" in fields and ("_status" in row or "status" in row):
        vals["status"] = _coerce(fields["status"], row.get("_status") or row.get("status"))
    if "geojson" in fields and ("_geolocation" in row or "geojson" in row):
        vals["geojson"] = _coerce(fields["geojson"], row.get("_geolocation") or row.get("geojson"))
    if "raw_json" in fields:
        vals["raw_json"] = row

    # 3) instance_id (strip 'uuid:')
    inst = row.get("meta/instanceID") or row.get("instanceID") or row.get("_uuid") or row.get("uuid")
    if isinstance(inst, str) and inst.lower().startswith("uuid:"):
        inst = inst.split(":", 1)[1]
    if "instance_id" in fields:
        vals["instance_id"] = inst

    # 4) auto *_count (si champ présent côté modèle)
    for fname, f in fields.items():
        if isinstance(f, models.IntegerField) and fname.endswith("_count"):
            prefix = fname[:-6]
            group = row.get(prefix) or row.get(prefix.replace("/", "-"))
            if isinstance(group, list):
                vals[fname] = len(group)

    # 5) fallback auto par noms canonisés pour tout champ parent restant
    row_index: Dict[str, str] = {}
    for k, v in row.items():
        if isinstance(v, list):  # pas de repeat ici
            continue
        row_index[_canon(k)] = k

    for fname, f in fields.items():
        if fname in vals or fname in SYSTEM_PARENT_FIELDS:
            continue
        src = row_index.get(fname)
        if not src:
            continue
        vals[fname] = _coerce(f, _flat(row.get(src)))

    # 6) garde-fous
    if "submission_time" in vals:
        vals["submission_time"] = _make_aware(vals["submission_time"])
    # ajuster les CharField
    for fname, f in fields.items():
        if fname in vals:
            vals[fname] = _fit_to_field(f, vals[fname])

    return vals


# -------------------------- détection des repeats --------------------------
def _child_blocks(form: KoboForm) -> Dict[str, List[Dict[str, str]]]:
    """
    Détecte les prefixes de repeat même sans dtype='repeat':
      - lignes KoboFieldMap avec dtype='repeat'
      - n'importe quelle kobo_name 'prefix/suffix'
      - champs finissant par '_count' (-> 'prefix')
      - clés list d'objets dans form.sample_json
    Puis regroupe les maps 'prefix/suffix' par prefix.
    """
    maps = list(
        KoboFieldMap.objects.filter(form=form).values("kobo_name", "model_field", "dtype")
    )

    prefixes: set[str] = set()

    # 1) explicite
    prefixes |= {
        (m["kobo_name"] or "").split("/", 1)[0]
        for m in maps
        if (m.get("dtype") or "").strip().lower() == "repeat"
    }

    # 2) toute clé avec '/'
    prefixes |= {
        (m["kobo_name"] or "").split("/", 1)[0]
        for m in maps
        if "/" in (m.get("kobo_name") or "")
    }

    # 3) *_count
    prefixes |= {
        (m["kobo_name"] or "")[:-6]
        for m in maps
        if (m.get("kobo_name") or "").endswith("_count")
    }

    # 4) sample_json
    sample = form.sample_json if isinstance(form.sample_json, dict) else None
    if isinstance(sample, dict):
        for k, v in sample.items():
            if isinstance(v, list) and any(isinstance(x, dict) for x in (v or [])):
                prefixes.add(k)

    children: Dict[str, List[Dict[str, str]]] = {p: [] for p in prefixes}

    # Regrouper les mappings connus 'prefix/suffix'
    for m in maps:
        kn = (m["kobo_name"] or "").strip()
        if "/" not in kn:
            continue
        pref = kn.split("/", 1)[0]
        if pref in children:
            children[pref].append(m)

    return children


# -------------------------- fetch KOBO (avec fallback) --------------------------
def _fetch_all_submissions_fallback(form: KoboForm, since: Optional[str] = None) -> List[dict]:
    """
    Fallback minimal si l’API dédiée n’est pas accessible :
    - renvoie un échantillon s’il existe dans form.sample_json (dict), sinon [].
    """
    if isinstance(form.sample_json, dict):
        return [form.sample_json]
    return []


try:
    from .kobo_api import fetch_all_submissions as _fetch_all_submissions  # pagination si dispo
except Exception:
    _fetch_all_submissions = _fetch_all_submissions_fallback


# -------------------------- synchro principale --------------------------
@transaction.atomic
def sync_submissions(
    form: KoboForm, since: Optional[str] = None, limit: Optional[int] = None
) -> Dict[str, Any]:
    # modèle parent dynamique
    Parent = apps.get_model(form.slug, _model_name_from_slug(form.slug))
    parent_fields = _fields_dict(Parent)
    child_maps = _child_blocks(form)  # { prefix: [maps...] }

    # 1) fetch
    rows = _fetch_all_submissions(form, since=since)  # -> List[dict]
    if limit:
        rows = rows[: int(limit)]

    created = updated = skipped = errors = 0
    err_samples: List[str] = []

    # 2) boucle sur les soumissions
    for row in rows:
        try:
            # valeurs parent
            pvals = _parent_values(form, row, Parent)
            inst = pvals.get("instance_id")
            if not inst:
                skipped += 1
                continue

            # upsert parent
            defaults_parent = {k: v for k, v in pvals.items() if k in parent_fields}
            try:
                obj, was_created = Parent.objects.update_or_create(
                    instance_id=inst, defaults=defaults_parent
                )
            except DataError:
                safe_defaults = _trim_to_db_limits(defaults_parent, parent_fields)
                obj, was_created = Parent.objects.update_or_create(
                    instance_id=inst, defaults=safe_defaults
                )

            if was_created:
                created += 1
            else:
                updated += 1

            # 3) enfants repeat: pour chaque prefix détecté
            for prefix, maps in child_maps.items():
                group = row.get(prefix) or row.get(prefix.replace("/", "-"))

                rel_name = f"{_canon(prefix)}_items"  # ex: 'grpppcb_items'
                if not hasattr(obj, rel_name):
                    # le modèle enfant correspondant n'existe pas (pas généré)
                    continue

                mgr = getattr(obj, rel_name)  # RelatedManager

                # purge pour cohérence simple
                mgr.all().delete()

                if not isinstance(group, list):
                    continue

                ChildModel = mgr.model
                c_fields = _fields_dict(ChildModel)

                # on stocke d'abord des dict (pour faciliter un fallback de tronquage)
                bulk_data: List[Dict[str, Any]] = []

                for idx, item in enumerate(group):
                    if not isinstance(item, dict):
                        continue

                    cvals: Dict[str, Any] = {
                        "parent_id": obj.id,
                        "item_index": idx,
                        "raw_json": item,
                    }

                    # 3a) mapping via KoboFieldMap si présent
                    for m in maps:
                        kn = (m["kobo_name"] or "").strip()      # p.ex. "GrpPPCB/Race_001"
                        mn = (m["model_field"] or "").strip()    # p.ex. "race_001"
                        if not mn or mn not in c_fields:
                            continue

                        suf = kn.split("/", 1)[1]
                        v = item.get(kn)
                        if v is None:
                            v = item.get(suf)  # parfois l’item ne garde que le suffixe

                        v = _coerce(c_fields[mn], _flat(v))
                        v = _fit_to_field(c_fields[mn], v)
                        cvals[mn] = v

                    # 3b) FALLBACK auto : compléter via noms canonisés
                    #     (utile si aucun mapping fin n'existe)
                    item_index_by_canon: Dict[str, str] = {}
                    for k_item in item.keys():
                        suf = k_item.split("/", 1)[1] if "/" in k_item else k_item
                        item_index_by_canon[_canon(suf)] = k_item

                    for fname, f in c_fields.items():
                        if fname in {"id", "parent", "parent_id", "item_index", "raw_json"}:
                            continue
                        if fname in cvals:
                            continue
                        src_key = item_index_by_canon.get(fname)
                        if src_key is None:
                            continue
                        v = _coerce(f, _flat(item.get(src_key)))
                        cvals[fname] = _fit_to_field(f, v)

                    bulk_data.append(cvals)

                if bulk_data:
                    try:
                        ChildModel.objects.bulk_create(
                            [ChildModel(**d) for d in bulk_data], batch_size=500
                        )
                    except DataError:
                        # tronquer et réessayer
                        fixed = [_trim_to_db_limits(d, c_fields) for d in bulk_data]
                        ChildModel.objects.bulk_create(
                            [ChildModel(**d) for d in fixed], batch_size=200
                        )

        except Exception as e:
            errors += 1
            if len(err_samples) < 5:
                rid = row.get("_uuid") or row.get("meta/instanceID") or row.get("_id")
                err_samples.append(f"{rid}: {type(e).__name__}: {e}")

    # 4) mise à jour du horodatage de synchronisation
    try:
        form.last_synced_at = timezone.now()
        form.save(update_fields=["last_synced_at"])
    except Exception:
        pass

    return {
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "error_samples": err_samples,
        "count_in": len(rows),
    }
