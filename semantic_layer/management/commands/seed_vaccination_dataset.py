# semantic_layer/management/commands/seed_vaccination_dataset.py
from django.core.management.base import BaseCommand
from kobo_bridge.models import KoboSource
from semantic_layer.models import DatasetLogical, Dimension, Measure, FilterDef

class Command(BaseCommand):
    """
    Crée un DatasetLogical 'Vaccination Kayes 2025' + dimensions, mesures, filtres
    adaptés au JSON de vaccination (avec listes imbriquées).
    """
    help = "Crée un DatasetLogical + dimensions/mesures/filtres pour Vaccination"

    def handle(self, *args, **kw):
        # 1) Source créée par load_sample_vaccination
        src = KoboSource.objects.get(name="Vaccination Kayes")

        # 2) Dataset logique
        ds, _ = DatasetLogical.objects.get_or_create(
            name="Vaccination Kayes 2025",
            defaults={"source": src, "description": "Dataset logique sur vaccinations Kayes"},
        )

        # 3) Dimensions
        dims = [
            dict(code="date",    label="Date de vaccination",
                 path="DateVaccination", dtype="date", transform="to_date", is_time=True),
            dict(code="region",  label="Région",
                 path="region", dtype="code"),
            dict(code="cercle",  label="Cercle",
                 path="cercle", dtype="code"),
            dict(code="commune", label="Commune",
                 path="commune", dtype="code"),
            dict(code="vaccinateur", label="Code vaccinateur",
                 path="codeVaccinateur", dtype="code"),
            # Lecture de la 1ère maladie et espèce dans le 1er site/1er élevage
            dict(
                code="maladie", label="Maladie (1er élevage du 1er site)",
                path="grpInfoGlobalVaccination/grpInfoSiteVaccination", dtype="code",
                transform="first_in_array",
                transform_params={
                    "sublist": "grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage",
                    "sub_field": "grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/qMad1"
                }
            ),
            dict(
                code="espece", label="Espèce (1er élevage du 1er site)",
                path="grpInfoGlobalVaccination/grpInfoSiteVaccination", dtype="code",
                transform="first_in_array",
                transform_params={
                    "sublist": "grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage",
                    "sub_field": "grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/liste_anisensibles"
                }
            ),
        ]
        for d in dims:
            Dimension.objects.update_or_create(
                dataset=ds, code=d["code"], defaults=d
            )

        # 4) Mesures (sommes sur les listes + mesure dérivée)
        measures = [
            dict(
                code="vaccins_attr", label="Animaux vaccinés (sites attribués)",
                path="grpInfoGlobalVaccination/grpInfoSiteVaccination",
                transform="sum_array_field_number",
                transform_params={"field": "grpInfoGlobalVaccination/grpInfoSiteVaccination/effectifTotalAnimauxVaccinesParSite"},
                default_agg="sum",
            ),
            dict(
                code="vaccins_nat", label="Animaux vaccinés (communes non attribuées)",
                path="grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT",
                transform="sum_array_field_number",
                transform_params={"field": "grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/effectifTotalAnimauxVaccineComNaT"},
                default_agg="sum",
            ),
            dict(
                code="vaccins_total", label="Animaux vaccinés (total)",
                path="", transform="derive_sum",
                transform_params={"sources": ["vaccins_attr", "vaccins_nat"]},
                default_agg="sum",
            ),
            dict(
                code="eleveurs_total", label="Éleveurs (total sites attribués)",
                path="grpInfoGlobalVaccination/grpInfoSiteVaccination",
                transform="sum_array_field_number",
                transform_params={"field": "grpInfoGlobalVaccination/grpInfoSiteVaccination/nbrTotalEleveurParSite"},
                default_agg="sum",
            ),
        ]
        for m in measures:
            Measure.objects.update_or_create(
                dataset=ds, code=m["code"], defaults=m
            )

        # 5) Filtres
        FilterDef.objects.update_or_create(
            dataset=ds, code="periode",
            defaults=dict(label="Période", dim_code="date", op="between"),
        )
        FilterDef.objects.update_or_create(
            dataset=ds, code="region",
            defaults=dict(label="Région", dim_code="region", op="in"),
        )
        FilterDef.objects.update_or_create(
            dataset=ds, code="maladie",
            defaults=dict(label="Maladie", dim_code="maladie", op="in"),
        )

        self.stdout.write(self.style.SUCCESS(
            "OK — DatasetLogical + dimensions/mesures/filtres créés pour 'Vaccination Kayes 2025'"
        ))
