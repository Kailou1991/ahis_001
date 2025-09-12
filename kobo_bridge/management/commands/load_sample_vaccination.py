# kobo_bridge/management/commands/load_sample_vaccination.py
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from kobo_bridge.models import KoboSource, RawSubmission
import json

SAMPLE_JSON = r"""
[{"_id":28630,"formhub/uuid":"9f1ed93c4a0b474c8d21fb117aa078a8","start":"2025-09-06T12:04:08.417-00:00","end":"2025-09-06T12:11:00.379-00:00","DateVaccination":"2025-09-06","region":"kayes","cercle":"kayes_ce","codeVaccinateur":"VTMS004","statutVaccinateur":"prive","NomVaccinateur":"ALI","TitreVaccinateur":"dv","AdresseVaccinateur":"Bamako","MailVaccinateur":"garbatinnikailou@gmail.com","telephone_vaccinateur":"78494631","commune":"commune_urbaine_kayes_004","verificationComNAttribue":"oui","qcomNaT":"bangassi","nbrqcomNaT":"1","grpInfoGlobalVaccination/grpInfoSiteVaccination_count":"1","grpInfoGlobalVaccination/grpInfoSiteVaccination":[{"grpInfoGlobalVaccination/grpInfoSiteVaccination/qchekParcVaccin":"parc_vaccination_amenage","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage":[{"grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/Systeme_elevage":"semi_intensif","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/qMad1":"Peripneumoniecontagieusebovine","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/liste_anisensibles":"BovinsPCB","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/LotVaccin":"12","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/date_peremption":"2025-12-31","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/effectifAnimauxVaccines":"123","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/nomEleveur":"2","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/telephone_eleveur":"78494631","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/nbrEleveurHomme":"1","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/nbrEleveurFemme":"1","grpInfoGlobalVaccination/grpInfoSiteVaccination/grpInfoElevage/nbrTotalEleveur":"2"}],"grpInfoGlobalVaccination/grpInfoSiteVaccination/nbrTotalEleveurHommeParSite":"1","grpInfoGlobalVaccination/grpInfoSiteVaccination/nbrTotalEleveurFemmeParSite":"1","grpInfoGlobalVaccination/grpInfoSiteVaccination/nbrTotalEleveurParSite":"2","grpInfoGlobalVaccination/grpInfoSiteVaccination/effectifTotalAnimauxVaccinesParSite":"123","grpInfoGlobalVaccination/grpInfoSiteVaccination/effectifTotalAnimauxMarquesParSite":"NaN"}],"grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT_count":"1","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT":[{"grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT":[{"grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/Systeme_elevageComNaT":"intensif","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/qMad1ComNaT":"Peripneumoniecontagieusebovine","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/liste_anisensiblesComNaT":"BovinsPCB","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/LotVaccinComNaT":"2","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/date_peremptionComNaT":"2025-10-22","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/effectifAnimauxVaccinesComNaT":"25","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/nomEleveurComNaT":"2","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/telephone_eleveurComNaT":"78494631","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/villageEleveurComNaT":"v","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/nbrEleveurHommeComNaT":"1","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/nbrEleveurFemmeComNaT":"11","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/grpInfoElevageComNaT/nbrTotalEleveurComNaT":"12"}],"grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/effectifTotalAnimauxVaccineComNaT":"25","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/effectifTotalAnimauxMarqueComNaT":"NaN","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/nbrTotalEleveurHommeParSiteComNaT":"1","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/nbrTotalEleveurFemmeParSiteComNaT":"11","grpInfoGlobalVaccination/grpInfoSiteVaccinationComNaT/nbrTotalEleveurParSiteComNaT":"12"}],"__version__":"v4WjTiVzxAP852Xwqgjre3","_version_":"vTcdwomXwqsKs27sgn2TTe","_version__001":"v64GVimEp7KV7Q3Ver8dRi","_version__002":"vACNZYnqDfFfKULLmvfCrt","_version__003":"vLKQAMJUd3V53h6jvBtKNV","_version__004":"vQ7rqiNMjUtjEifnLQizXc","_version__005":"v98vFhDUXC8qR7CZmFYKaW","meta/instanceID":"uuid:92bcdd36-8681-4a9b-aa02-509c51d53069","_xform_id_string":"aAEvHCMNPbaR848nuSdMYe","_uuid":"92bcdd36-8681-4a9b-aa02-509c51d53069","_attachments":[],"_status":"submitted_via_web","_geolocation":[null,null],"_submission_time":"2025-09-06T12:12:12","_tags":[],"_notes":[],"_validation_status":{},"_submitted_by":"ahismali"}]
"""

class Command(BaseCommand):
    """
    Charge le JSON vaccination fourni par l'utilisateur comme une RawSubmission.
    Crée (si besoin) une KoboSource "Vaccination Kayes".
    """
    help = "Charge un JSON de test (vaccination) comme RawSubmission"

    def add_arguments(self, parser):
        parser.add_argument("--source-name", default="Vaccination Kayes")
        parser.add_argument("--server-url", default="https://kf.kobotoolbox.org")
        parser.add_argument("--asset-uid", default="aAEvHCMNPbaR848nuSdMYe")

    def handle(self, *args, **opts):
        data = json.loads(SAMPLE_JSON)
        if isinstance(data, list):
            data = data[0]

        src, _ = KoboSource.objects.get_or_create(
            name=opts["source_name"],
            defaults=dict(
                server_url=opts["server_url"],
                asset_uid=opts["asset_uid"],
                token="dummy",
                mode="both",
                active=True,
            ),
        )

        instance_id = data.get("meta/instanceID") or data.get("_uuid")
        submission_time = data.get("_submission_time")

        RawSubmission.objects.update_or_create(
            source=src,
            instance_id=instance_id,
            defaults=dict(
                submission_id=str(data.get("_id")) if data.get("_id") is not None else None,
                submitted_at=parse_datetime(submission_time) if submission_time else None,
                xform_id=data.get("_xform_id_string"),
                form_version=data.get("_version_") or data.get("__version__"),
                payload=data,
            ),
        )

        self.stdout.write(self.style.SUCCESS(
            f"OK — JSON chargé pour source '{src.name}' (instance_id={instance_id})"
        ))
