# kobo_bridge/management/commands/kobo_pull_all.py
from __future__ import annotations

import time
import datetime
from typing import Iterable, Dict, Any, List, Optional
from urllib.parse import urlencode, quote

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, models
from django.utils.timezone import now, make_naive, utc
from django.utils.dateparse import parse_datetime

import requests

from kobo_bridge.models import KoboSource, RawSubmission


# ------------------------------
# Réseau / OData / REST helpers
# ------------------------------

DEFAULT_PAGE_SIZE = 500
HTTP_TIMEOUT = 30


def _http_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "Accept": "application/json",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }
    )
    return s


def _odata_entity(server_url: str, asset_uid: str) -> str:
    base = server_url.rstrip("/")
    return f"{base}/api/v2/assets/{asset_uid}/odata/"


def _odata_main_table_url(
    server_url: str, asset_uid: str, token: str, session: requests.Session
) -> str:
    """Découvre l’EntitySet principale (souvent 'Submissions')."""
    ent = _odata_entity(server_url, asset_uid)
    r = session.get(ent, headers={"Authorization": f"Token {token}"}, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    j = r.json()
    coll = next((x.get("name") for x in j.get("value", []) if x.get("kind") == "EntitySet"), None)
    if not coll:
        coll = "Submissions"
    return ent + quote(coll)


def _iso_odata(dt: Optional[datetime.datetime]) -> Optional[str]:
    if dt is None:
        return None
    # S'assurer que l'heure est UTC et naive au format OData
    if getattr(dt, "tzinfo", None) is not None:
        dt = make_naive(dt.astimezone(utc), timezone=utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _norm_instance_id(v: Optional[str]) -> Optional[str]:
    """Normalise l'instance_id: enlève 'uuid:' / décors, retourne en minuscules."""
    if not v:
        return None
    v = str(v).strip()
    v = v.strip("{}()<>").strip()
    if v.lower().startswith("uuid:"):
        v = v[5:]
    return v.lower()


def _parse_dt_any(s: Optional[str]) -> Optional[datetime.datetime]:
    """Parse une date (ISO, 'Z', offsets). Retourne un datetime aware (UTC) si possible."""
    if not s:
        return None
    dt = parse_datetime(s)
    if dt is None:
        try:
            ds = s.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(ds)
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utc)
    return dt


def iter_submissions(
    server_url: str,
    asset_uid: str,
    token: str,
    since_dt: Optional[datetime.datetime],
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Iterable[Dict[str, Any]]:
    """
    Rend des dicts de soumission. Incrémental si since_dt est fourni.
    Essaye OData (rapide, filtrage serveur), puis fallback REST JSON.
    """
    sess = _http_session()
    auth = {"Authorization": f"Token {token}"}

    # ---- 1) ODATA (préféré) ----
    try:
        base = _odata_main_table_url(server_url, asset_uid, token, sess)
        params = {"$top": page_size}
        if since_dt:
            iso = _iso_odata(since_dt)
            params["$filter"] = f"_submission_time ge datetime'{iso}'"

        next_url = f"{base}?{urlencode(params)}"
        backoff = 2
        while next_url:
            r = sess.get(next_url, headers=auth, timeout=HTTP_TIMEOUT)
            if r.status_code >= 500:
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
                continue
            r.raise_for_status()
            j = r.json()
            for item in j.get("value", []):
                yield item
            next_url = j.get("@odata.nextLink")
        return
    except Exception:
        # Fallback REST
        pass

    # ---- 2) REST JSON ----
    candidates = [
        f"{server_url.rstrip('/')}/api/v2/assets/{asset_uid}/data/",
        f"{server_url.rstrip('/')}/api/v2/assets/{asset_uid}/data.json",
        f"{server_url.rstrip('/')}/api/v1/data/{asset_uid}",
    ]
    params = {"limit": page_size}
    if since_dt:
        params["_submission_time__gte"] = _iso_odata(since_dt)  # si supporté

    next_url = None
    for u in candidates:
        try:
            r = sess.get(u, headers=auth, params=params, timeout=HTTP_TIMEOUT)
            if r.status_code == 200:
                next_url = r.url
                break
        except Exception:
            continue

    if not next_url:
        raise RuntimeError("Aucun endpoint OData/REST utilisable.")

    backoff = 2
    while next_url:
        r = sess.get(next_url, headers=auth, timeout=HTTP_TIMEOUT)
        if r.status_code >= 500:
            time.sleep(backoff)
            backoff = min(backoff * 2, 30)
            continue
        r.raise_for_status()
        j = r.json()
        items = j if isinstance(j, list) else j.get("results") or j.get("data") or []
        # Filtre client si besoin
        if since_dt:
            iso = _iso_odata(since_dt)
            for item in items:
                sub = (
                    item.get("_submission_time")
                    or item.get("submission_time")
                    or item.get("end")
                    or item.get("start")
                    or item.get("date_modified")
                )
                if not sub or sub >= iso:
                    yield item
        else:
            for item in items:
                yield item

        next_url = j.get("next") if isinstance(j, dict) else None


# ------------------------------
# Extraction champs + persistence
# ------------------------------

def _extract_instance_id(row: Dict[str, Any]) -> Optional[str]:
    iid_candidates = [
        row.get("meta/instanceID"),
        row.get("meta_instanceID"),
        row.get("instanceID"),
        row.get("_uuid"),
        row.get("uuid"),
    ]
    instance_id = next((x for x in iid_candidates if x), None)
    if instance_id is None:
        _id = row.get("_id") or row.get("id")
        if _id is not None:
            instance_id = f"oid:{_id}"
    return _norm_instance_id(instance_id)


def _extract_submitted_at(row: Dict[str, Any]) -> Optional[datetime.datetime]:
    s = (
        row.get("_submission_time")
        or row.get("submission_time")
        or row.get("end")
        or row.get("start")
        or row.get("date_modified")
    )
    return _parse_dt_any(s)


def _objects_from_rows(source: KoboSource, rows: Iterable[Dict[str, Any]]):
    """
    Prépare deux listes : (news, updates) pour bulk_create / bulk_update
    Renvoie (to_create, to_update, seen_count)
    """
    instance_ids: List[str] = []
    cache_rows: List[tuple[str, Dict[str, Any]]] = []
    for row in rows:
        iid = _extract_instance_id(row)  # normalisé
        if not iid:
            continue
        instance_ids.append(iid)
        cache_rows.append((iid, row))

    if not cache_rows:
        return [], [], 0

    existing = {
        _norm_instance_id(obj.instance_id): obj
        for obj in RawSubmission.objects.filter(source=source, instance_id__in=instance_ids)
    }

    to_create: List[RawSubmission] = []
    to_update: List[RawSubmission] = []

    for iid, row in cache_rows:
        submitted_at = _extract_submitted_at(row)  # datetime aware ou None
        submission_id = row.get("_id") or row.get("id")
        xform_id = row.get("_xform_id_string") or row.get("xform_id") or row.get("form_id")
        form_version = row.get("_version") or row.get("version")

        if iid in existing:
            obj = existing[iid]
            obj.submission_id = str(submission_id) if submission_id is not None else None
            obj.submitted_at = submitted_at
            obj.xform_id = xform_id
            obj.form_version = form_version
            obj.payload = row
            to_update.append(obj)
        else:
            to_create.append(
                RawSubmission(
                    source=source,
                    instance_id=iid,
                    submission_id=str(submission_id) if submission_id is not None else None,
                    submitted_at=submitted_at,
                    xform_id=xform_id,
                    form_version=form_version,
                    payload=row,
                )
            )

    return to_create, to_update, len(cache_rows)


# ------------------------------
# Commande
# ------------------------------

class Command(BaseCommand):
    help = "Tire toutes les Kobo sources actives de manière incrémentale (optimisée)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sources",
            nargs="*",
            help="Filtrer par noms de sources (name) ou par IDs (pk).",
        )
        parser.add_argument(
            "--since",
            type=str,
            help="ISO datetime pour forcer un point de départ (ex: 2025-09-07T00:00:00).",
        )
        parser.add_argument(
            "--backfill-days",
            type=int,
            default=None,
            help="Si défini, force since = now - N jours (ignoré si --since donné).",
        )
        parser.add_argument(
            "--page-size",
            type=int,
            default=DEFAULT_PAGE_SIZE,
            help=f"Taille de page (défaut {DEFAULT_PAGE_SIZE}).",
        )

    def handle(self, *args, **opts):
        sources_filter = opts.get("sources") or []
        since_str = opts.get("since")
        backfill_days = opts.get("backfill_days")
        page_size = int(opts.get("page_size") or DEFAULT_PAGE_SIZE)

        # Résolution du since "global" si fourni
        since_dt_global: Optional[datetime.datetime] = None
        if since_str:
            try:
                since_dt_global = datetime.datetime.fromisoformat(since_str.replace("Z", "+00:00"))
            except Exception as e:
                raise CommandError(f"--since invalide: {e}")
        elif backfill_days:
            since_dt_global = now() - datetime.timedelta(days=int(backfill_days))

        qs = KoboSource.objects.filter(active=True)
        if sources_filter:
            qs = qs.filter(
                models.Q(pk__in=[s for s in sources_filter if str(s).isdigit()])
                | models.Q(name__in=sources_filter)
            )

        if not qs.exists():
            self.stdout.write(self.style.WARNING("Aucune source active trouvée."))
            return

        total_new = 0
        total_upd = 0
        total_seen = 0

        for src in qs.order_by("pk"):
            self.stdout.write(f"→ Source #{src.pk} “{src.name}” (active={src.active})")

            # since par source (incrémental)
            if since_dt_global is not None:
                since_dt = since_dt_global
            else:
                last = (
                    RawSubmission.objects.filter(source=src)
                    .aggregate(models.Max("submitted_at"))
                    .get("submitted_at__max")
                )
                since_dt = last

            # Pull incrémental
            new_, upd_, seen_ = 0, 0, 0
            batch_rows: List[Dict[str, Any]] = []
            BATCH = max(2000, page_size)  # on flush quand on dépasse une grosse page

            def _flush_batch():
                nonlocal new_, upd_, seen_
                if not batch_rows:
                    return
                to_create, to_update, count_in = _objects_from_rows(src, batch_rows)
                seen_ += count_in
                # Transaction + bulk opérations
                with transaction.atomic():
                    if to_create:
                        # ---- Option par défaut : tolérer les conflits ----
                        RawSubmission.objects.bulk_create(
                            to_create,
                            batch_size=1000,
                            ignore_conflicts=True,  # évite IntegrityError si (source, instance_id) existe déjà
                        )
                        new_ += len(to_create)
                        # ---- Option Django 5 (upsert vrai) ----
                        # RawSubmission.objects.bulk_create(
                        #     to_create,
                        #     update_conflicts=True,
                        #     unique_fields=["source", "instance_id"],
                        #     update_fields=["submission_id", "submitted_at", "xform_id", "form_version", "payload"],
                        #     batch_size=1000,
                        # )
                        # new_ += len(to_create)

                    if to_update:
                        RawSubmission.objects.bulk_update(
                            to_update,
                            fields=["submission_id", "submitted_at", "xform_id", "form_version", "payload"],
                            batch_size=1000,
                        )
                        upd_ += len(to_update)

                batch_rows.clear()

            for row in iter_submissions(
                server_url=src.server_url,
                asset_uid=src.asset_uid,
                token=src.token,
                since_dt=since_dt,
                page_size=page_size,
            ):
                batch_rows.append(row)
                if len(batch_rows) >= BATCH:
                    _flush_batch()

            _flush_batch()

            total_new += new_
            total_upd += upd_
            total_seen += seen_
            self.stdout.write(
                self.style.SUCCESS(f"   ✓ {new_} nouveaux, {upd_} mis à jour, 0 ignorés (lus={seen_})")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"TOTAL: {total_new} nouveaux, {total_upd} mis à jour, 0 ignorés (lus={total_seen})"
            )
        )
