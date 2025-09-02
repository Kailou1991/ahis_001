from django.core.management.base import BaseCommand
from django.utils import timezone
from kobo_integration.models import KoboForm
from kobo_integration.services.runtime_sync import sync_submissions

def _to_iso(dt):
    # impression lisible avec timezone (UTC)
    if not dt:
        return None
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt.isoformat(timespec="seconds")

class Command(BaseCommand):
    help = "Synchronise tous les KoboForm actifs vers leurs modèles générés."

    def add_arguments(self, parser):
        parser.add_argument("--since", type=str, default=None,
                            help='ISO override pour TOUT (ex: "2025-01-01T00:00:00Z")')
        parser.add_argument("--limit", type=int, default=None, help="Limiter les lignes par formulaire")

    def handle(self, *args, **opts):
        total = dict(created=0, updated=0, skipped=0, errors=0)
        forms = KoboForm.objects.all().order_by("slug")

        for f in forms:
            since = opts.get("since") or _to_iso(f.last_synced_at)
            res = sync_submissions(f, since=since, limit=opts.get("limit"))
            created = res.get("created", 0)
            updated = res.get("updated", 0)
            skipped = res.get("skipped", 0)
            errors  = res.get("errors", res.get("failed", 0))

            total["created"] += created
            total["updated"] += updated
            total["skipped"] += skipped
            total["errors"]  += errors

            self.stdout.write(
                f"[{f.slug}] created={created} updated={updated} "
                f"skipped={skipped} errors={errors} since={since}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"TOTAL created={total['created']} updated={total['updated']} "
                f"skipped={total['skipped']} errors={total['errors']}"
            )
        )
