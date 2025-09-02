# kobo_integration/management/commands/kobo_sync_all.py
from __future__ import annotations

import sys
import time
import zlib
from typing import Optional, Dict, Any

from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

from kobo_integration.models import KoboForm
from kobo_integration.services.runtime_sync import sync_submissions


def _pg_try_advisory_lock(lock_id: int) -> bool:
    """Évite les exécutions en parallèle via un verrou Postgres (no-op si autre DB)."""
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
            row = cur.fetchone()
            return bool(row and row[0])
    except Exception:
        # Si ce n’est pas Postgres, on ignore le verrou
        return True


def _pg_advisory_unlock(lock_id: int) -> None:
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
    except Exception:
        pass


class Command(BaseCommand):
    help = "Synchronise tous les KoboForm (ou une liste de slugs)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--slug", action="append",
            help="Limiter à un ou plusieurs slugs (utiliser plusieurs --slug)."
        )
        parser.add_argument(
            "--since", default="last",
            help="Point de reprise: 'last' (par défaut, last_synced_at), "
                 "'none' (full), ou un datetime ISO (ex: 2025-01-01T00:00:00Z)."
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Limiter le nombre d’entrées ramenées par formulaire (debug)."
        )
        parser.add_argument(
            "--advisory-lock", action="store_true",
            help="Activer un verrou Postgres pour éviter les chevauchements."
        )
        parser.add_argument(
            "--regenerate", action="store_true",
            help="Régénérer les modèles via le generator avant la sync."
        )

    def handle(self, *args, **opts):
        slugs = opts.get("slug") or []
        since_opt = (opts.get("since") or "last").strip().lower()
        limit = opts.get("limit")
        use_lock = bool(opts.get("advisory_lock"))
        do_regen = bool(opts.get("regenerate"))

        lock_id = zlib.crc32(b"kobo_sync_all")

        if use_lock:
            if not _pg_try_advisory_lock(lock_id):
                self.stdout.write(self.style.WARNING(
                    "[SKIP] Un autre kobo_sync_all tourne déjà (advisory lock)."
                ))
                return
            self.stdout.write("[LOCK] Advisory lock acquis.")

        try:
            qs = KoboForm.objects.all().order_by("slug")
            if slugs:
                qs = qs.filter(slug__in=slugs)

            total = {"created": 0, "updated": 0, "skipped": 0, "errors": 0, "count_in": 0}
            started = timezone.now()
            self.stdout.write(f"== DÉMARRAGE sync ({started.isoformat()}) | forms={qs.count()} ==")

            if do_regen:
                from kobo_integration.services.generator import generate_app
                for f in qs:
                    t0 = time.time()
                    try:
                        app_slug, model_name, out = generate_app(f.id)
                        self.stdout.write(self.style.SUCCESS(
                            f"[GEN] {app_slug}:{model_name} OK ({time.time()-t0:.1f}s)"
                        ))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"[GEN] {f.slug} échec: {e}"))

            for f in qs:
                if since_opt == "none":
                    since = None
                elif since_opt == "last":
                    since = f.last_synced_at.isoformat() if f.last_synced_at else None
                else:
                    since = since_opt

                t0 = time.time()
                try:
                    res = sync_submissions(f, since=since, limit=limit)
                    dt = time.time() - t0

                    for k in total.keys():
                        total[k] += int(res.get(k, 0))

                    self.stdout.write(
                        f"[SYNC] {f.slug:<30} created={res['created']:>4} "
                        f"updated={res['updated']:>4} skipped={res['skipped']:>3} "
                        f"errors={res['errors']:>2} in={res['count_in']:>4}  ({dt:.1f}s)"
                    )
                    if res.get("error_samples"):
                        for sample in res["error_samples"]:
                            self.stdout.write(self.style.WARNING(f"        └─ {sample}"))

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"[SYNC] {f.slug} ERROR: {e}"))
                    total["errors"] += 1

            ended = timezone.now()
            self.stdout.write(
                f"== FIN sync ({ended.isoformat()}) | dur={(ended-started).total_seconds():.1f}s =="
            )
            self.stdout.write(
                f"TOTAL created={total['created']} updated={total['updated']} "
                f"skipped={total['skipped']} errors={total['errors']} in={total['count_in']}"
            )

            if total["errors"] > 0:
                sys.exit(2)

        finally:
            if use_lock:
                _pg_advisory_unlock(lock_id)
                self.stdout.write("[LOCK] Advisory lock libéré.")
