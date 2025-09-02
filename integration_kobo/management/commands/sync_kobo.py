from django.core.management.base import BaseCommand
from integration_kobo.models import FormulaireKobo, SyncLog
from integration_kobo.services import get_kobo_data
from integration_kobo import parsers



class Command(BaseCommand):
    help = 'Synchronise tous les formulaires Kobo actifs définis dans le modèle FormulaireKobo.'

    def handle(self, *args, **kwargs):
        formulaires = FormulaireKobo.objects.filter(actif=True)

        if not formulaires.exists():
            self.stdout.write(self.style.WARNING("Aucun formulaire Kobo actif trouvé."))
            return

        for formulaire in formulaires:
            try:
                self.stdout.write(f"\n▶ Synchronisation du formulaire : {formulaire.nom} ({formulaire.uid})")

                data_list = get_kobo_data(formulaire.uid, formulaire.token, formulaire.base_url)
                parse_func = getattr(parsers, formulaire.parser)
                messages = []

                for data in data_list:
                    retour = parse_func(data, formulaire=formulaire)
                    messages.extend(retour or [])

                # Affiche les foyers ignorés après traitement complet de ce formulaire
                parsers.afficher_foyers_ignores()

                SyncLog.objects.create(
                    formulaire=formulaire,
                    status="SUCCES",
                    message=f"{len(data_list)} enregistrements traités."
                )
                self.stdout.write(self.style.SUCCESS(f"✔ {len(data_list)} enregistrements synchronisés pour {formulaire.nom}."))

            except Exception as e:
                SyncLog.objects.create(
                    formulaire=formulaire,
                    status="ECHEC",
                    message=str(e)
                )
                self.stdout.write(self.style.ERROR(f"❌ Erreur lors de la synchronisation du formulaire {formulaire.nom} : {e}"))
