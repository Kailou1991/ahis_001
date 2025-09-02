# ✅ SCRIPT 1 : Commande pour générer et déployer les formulaires Kobo pour toutes les apps AHIS

from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import models
from django.conf import settings
import json
import os
import requests

OUTPUT_DIR = "output/kobo_forms"

class Command(BaseCommand):
    help = "Génère et déploie automatiquement les formulaires Kobo pour toutes les apps"

    def handle(self, *args, **kwargs):
        if not os.path.exists(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)

        for app_config in apps.get_app_configs():
            if "django." in app_config.name:
                continue  # Ignore les apps internes

            form_data = self.generate_kobo_form_for_app(app_config)

            if form_data:
                file_path = os.path.join(OUTPUT_DIR, f"formulaire_{app_config.label}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(form_data, f, indent=4, ensure_ascii=False)
                self.stdout.write(self.style.SUCCESS(f"✅ Formulaire JSON généré pour : {app_config.label}"))

                # Création et déploiement Kobo
                self.deploy_to_kobotoolbox(form_data, app_config.label)

    def generate_kobo_form_for_app(self, app_config):
        form_fields = []

        for model in app_config.get_models():
            group = model.__name__
            for field in model._meta.fields:
                if field.name in ['id', 'created_at', 'updated_at']:
                    continue

                field_type = self.map_field_type(field)
                form_fields.append({
                    "type": field_type,
                    "name": f"{group.lower()}_{field.name}",
                    "label": f"{group} - {field.verbose_name}"
                })

        if not form_fields:
            return None

        return {
            "title": f"Formulaire_{app_config.label}",
            "fields": form_fields
        }

    def map_field_type(self, field):
        if isinstance(field, models.IntegerField):
            return "integer"
        elif isinstance(field, models.BooleanField):
            return "select_one"
        elif isinstance(field, models.DateField):
            return "date"
        elif isinstance(field, models.FloatField):
            return "decimal"
        elif isinstance(field, models.ForeignKey):
            return "select_one"
        else:
            return "text"

    def deploy_to_kobotoolbox(self, form_json, app_label):
        headers = {
            "Authorization": settings.KOBOTOOLBOX_TOKEN,
            "Content-Type": "application/json",
        }

        payload = {
            "name": form_json["title"],
            "asset_type": "survey",
            "content": {
                "survey": [
                    {
                        "type": field["type"],
                        "name": field["name"],
                        "label": field["label"]
                    }
                    for field in form_json["fields"]
                ]
            }
        }

        response = requests.post(
            settings.KOBOTOOLBOX_API_URL,
            json=payload,
            headers=headers,
            verify=False  # Désactivation temporaire de la vérification SSL (à sécuriser en production)
        )

        if response.status_code == 201:
            try:
                asset_uid = response.json().get("uid")
                self.stdout.write(self.style.SUCCESS(f"🚀 Formulaire {app_label} créé sur KoboToolbox (UID: {asset_uid})"))
                self.deploy_draft_form(asset_uid)
            except json.JSONDecodeError:
                self.stdout.write(self.style.ERROR("❌ Erreur lors de la lecture du JSON retourné."))
                self.stdout.write(self.style.ERROR(f"Réponse brute : {response.text}"))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Échec création formulaire : {response.status_code}"))
            self.stdout.write("🔍 Contenu brut de la réponse :")
            self.stdout.write(response.text)

    def deploy_draft_form(self, asset_uid):
        url = f"{settings.KOBOTOOLBOX_API_URL}{asset_uid}/deployment/"
        headers = {
            "Authorization": settings.KOBOTOOLBOX_TOKEN,
        }

        response = requests.post(url, headers=headers, verify=False)

        if response.status_code == 201:
            self.stdout.write(self.style.SUCCESS(f"📤 Formulaire {asset_uid} déployé avec succès."))
        elif response.status_code == 400 and "non_field_errors" in response.json():
            self.stdout.write(self.style.WARNING(f"⚠️  Formulaire {asset_uid} déjà déployé."))
        else:
            self.stdout.write(self.style.ERROR(f"❌ Erreur de déploiement : {response.status_code} - {response.text}"))
