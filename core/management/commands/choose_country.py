# core/management/commands/choose_country.py
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
import json, os

class Command(BaseCommand):
    help = "Choisit le pays actif depuis static/img/countries.json et crée static/img/country_active.json"

    def add_arguments(self, parser):
        parser.add_argument("pays", help="Nom du pays (ex: 'Niger')")

    def handle(self, *args, **opts):
        pays_arg = opts["pays"].strip().lower()

        # chemin de countries.json
        src_path = os.path.join(settings.BASE_DIR, "static", "img", "countries.json")
        if not os.path.exists(src_path):
            raise CommandError(f"Fichier introuvable: {src_path}")

        with open(src_path, encoding="utf-8") as f:
            rows = json.load(f)

        if not isinstance(rows, list):
            raise CommandError("countries.json doit contenir une liste d'objets.")

        # recherche du pays demandé
        row = next(
            (r for r in rows if r.get("pays", "").strip().lower() == pays_arg),
            None
        )
        if not row:
            dispo = ", ".join(r.get("pays", "?") for r in rows)
            raise CommandError(f"Pays '{opts['pays']}' non trouvé. Disponibles: {dispo}")

        # normaliser les chemins (toujours sous static/img/)
        def norm_img(val):
            if not val:
                return ""
            v = val.strip().lstrip("/").replace("\\", "/")
            return f"img/{v}" if not v.startswith("img/") else v

        row["drapeau"]  = norm_img(row.get("drapeau", ""))
        row["armoirie"] = norm_img(row.get("armoirie", ""))

        # écrire country_active.json
        out_path = os.path.join(settings.BASE_DIR, "static", "img", "country_active.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(row, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(
            f"Pays actif sélectionné: {row['appellation']} → {out_path}"
        ))
