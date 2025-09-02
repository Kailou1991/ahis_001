from django.core.management.base import BaseCommand, CommandError
from kobo_integration.models import KoboForm
from kobo_integration.services.runtime_sync import sync_submissions

class Command(BaseCommand):
    help = "Synchronise les données Kobo -> modèle généré (via KoboFieldMap)."

    def add_arguments(self, parser):
        g = parser.add_mutually_exclusive_group(required=True)
        g.add_argument("--id", type=int, help="ID du KoboForm")
        g.add_argument("--slug", type=str, help="Slug du KoboForm (ex: sero)")
        parser.add_argument("--since", type=str, default=None,
                            help='ISO local sur _submission_time (ex: "2025-01-01T00:00:00Z")')
        parser.add_argument("--limit", type=int, default=None, help="Limiter le nombre de lignes")

    def handle(self, *args, **opts):
        try:
            if opts.get("id"):
                form = KoboForm.objects.get(pk=opts["id"])
            else:
                form = KoboForm.objects.get(slug=opts["slug"])
        except KoboForm.DoesNotExist:
            raise CommandError("KoboForm introuvable.")

        res = sync_submissions(form, since=opts.get("since"), limit=opts.get("limit"))

        inserted = res.get("inserted", res.get("created", 0))
        updated  = res.get("updated", 0)
        skipped  = res.get("skipped", 0)
        failed   = res.get("failed", res.get("errors", 0))
        samples  = res.get("error_samples", [])

        line = (f"OK — inserted={inserted} updated={updated} "
                f"skipped={skipped} failed={failed}")
        if samples:
            line += f" | samples: {samples}"
        self.stdout.write(self.style.SUCCESS(line))
