# actes_admin/management/commands/seed_actes.py
from django.core.management.base import BaseCommand
from django.db import transaction
from actes_admin.models import CategorieActe, TypeActe, PieceAFournir

CATEGORIES = [
    {'id': 1, 'code': 'MIA', 'nom': 'Mouvement interne des animaux', 'necessite_avis_ordre': False},
    {'id': 2, 'code': 'AOC', 'nom': 'Ouverture de couvoir', 'necessite_avis_ordre': False},
    {'id': 3, 'code': 'AESIV', 'nom': 'Exercice des soins infirmiers vétérinaires', 'necessite_avis_ordre': False},
    {'id': 4, 'code': 'AEMV', 'nom': 'Exercice de la médecine vétérinaire', 'necessite_avis_ordre': True},
    {'id': 5, 'code': 'AOEVPV', 'nom': 'Ouverture établissement de vente des produits vétérinaires', 'necessite_avis_ordre': True},
    {'id': 6, 'code': 'IOA', 'nom': 'Importation animaux sur pied', 'necessite_avis_ordre': False},
    {'id': 7, 'code': 'DEI', 'nom': 'Importation  des produits animaux', 'necessite_avis_ordre': False},
    {'id': 8, 'code': 'EPA', 'nom': 'Exportation des produits animaux', 'necessite_avis_ordre': False},
    {'id': 9, 'code': 'EASP', 'nom': 'Exportation animaux sur pied', 'necessite_avis_ordre': False},
    {'id': 10, 'code': 'OEA', 'nom': "Ouverture établissement abattage et de transformation de DAOA", 'necessite_avis_ordre': False},
    {'id': 11, 'code': 'AIEPVME', 'nom': 'Importation des produits vétérinaires et matériel élevage', 'necessite_avis_ordre': False},
]

TYPE_ACTES = [
    {'id': 6, 'code': '0001', 'nom': 'Autorisation d’exercer la médecine vétérinaire à titre privé', 'prix': 25000.0, 'validite': 'sans_limite', 'categorie_id': 4},
    {'id': 7, 'code': '0002', 'nom': "Transfert de l’autorisation d’exercer la médecine vétérinaire", 'prix': 25000.0, 'validite': 'sans_limite', 'categorie_id': 4},
    {'id': 10, 'code': '0005', 'nom': "Renouvellement ou transfert de l’autorisation d’exercer les soins infirmiers", 'prix': 10000.0, 'validite': '1_an', 'categorie_id': 3},
    {'id': 14, 'code': '0010', 'nom': 'Laissez-passer sanitaire', 'prix': 500.0, 'validite': '1_mois', 'categorie_id': 1},
    {'id': 13, 'code': '0009', 'nom': "Autorisation d'ntroduction d’animaux sur pieds", 'prix': 5000.0, 'validite': '6_mois', 'categorie_id': 6},
    {'id': 11, 'code': '0007', 'nom': "Autorisation d'importation de médicaments vétérinaires", 'prix': 20000.0, 'validite': '6_mois', 'categorie_id': 11},
    {'id': 9, 'code': '0004', 'nom': "Autorisation d'exercer des soins infirmiers", 'prix': 10000.0, 'validite': '1_an', 'categorie_id': 3},
    {'id': 8, 'code': '0003', 'nom': "Renouvellement de l’autorisation d’exercer la médecine vétérinaire", 'prix': 25000.0, 'validite': 'sans_limite', 'categorie_id': 4},
    {'id': 12, 'code': '0008', 'nom': "Autorisation d'ouverture d'un couvoir", 'prix': 15000.0, 'validite': 'sans_limite', 'categorie_id': 2},
]

PIECES = [
    {'id': 13, 'nom_piece': 'Demande adressée au Ministre chargé de l’Élevage', 'description': None, 'obligatoire': True, 'type_acte_id': 6},
    {'id': 14, 'nom_piece': "Copie légalisée du Diplôme d’État de Docteur vétérinaire", 'description': None, 'obligatoire': True, 'type_acte_id': 6},
    {'id': 15, 'nom_piece': "Copie légalisée de la carte nationale d’identité", 'description': None, 'obligatoire': True, 'type_acte_id': 6},
    {'id': 16, 'nom_piece': 'Bulletin de casier judiciaire (moins de 3 mois)', 'description': None, 'obligatoire': True, 'type_acte_id': 6},
    {'id': 17, 'nom_piece': "Attestation d’inscription à l'Ordre des vétérinaires", 'description': None, 'obligatoire': True, 'type_acte_id': 6},
    {'id': 18, 'nom_piece': 'Attestation de non engagement dans la Fonction publique', 'description': None, 'obligatoire': True, 'type_acte_id': 6},
    {'id': 19, 'nom_piece': 'Certificat de résidence', 'description': None, 'obligatoire': True, 'type_acte_id': 6},
    {'id': 20, 'nom_piece': "Copie légalisée du diplôme d'infirmier d'État en soins vétérinaires", 'description': None, 'obligatoire': True, 'type_acte_id': 9},
    {'id': 21, 'nom_piece': "Copie légalisée de la carte nationale d’identité", 'description': None, 'obligatoire': True, 'type_acte_id': 9},
    {'id': 22, 'nom_piece': "Bulletin de casier judiciaire (moins de 3 mois)", 'description': None, 'obligatoire': True, 'type_acte_id': 9},
    {'id': 23, 'nom_piece': 'Certificat de résidence', 'description': None, 'obligatoire': True, 'type_acte_id': 9},
]

class Command(BaseCommand):
    help = "Seed des catégories, types d'actes et pièces à fournir"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("==> Insertion des catégories"))
        for c in CATEGORIES:
            obj, created = CategorieActe.objects.update_or_create(
                id=c["id"],
                defaults={
                    "code": c["code"],
                    "nom": c["nom"],
                    "necessite_avis_ordre": c["necessite_avis_ordre"],
                },
            )
            self.stdout.write(("Créée : " if created else "Mise à jour : ") + obj.nom)

        self.stdout.write(self.style.SUCCESS("\n==> Insertion des types d'actes"))
        for t in TYPE_ACTES:
            obj, created = TypeActe.objects.update_or_create(
                id=t["id"],
                defaults={
                    "code": t["code"],
                    "nom": t["nom"],
                    "prix": t["prix"],
                    "validite": t["validite"],
                    "categorie_id": t["categorie_id"],
                },
            )
            self.stdout.write(("Créé : " if created else "Mis à jour : ") + obj.nom)

        self.stdout.write(self.style.SUCCESS("\n==> Insertion des pièces à fournir"))
        for p in PIECES:
            obj, created = PieceAFournir.objects.update_or_create(
                id=p["id"],
                defaults={
                    "nom_piece": p["nom_piece"],
                    "description": p["description"],
                    "obligatoire": p["obligatoire"],
                    "type_acte_id": p["type_acte_id"],
                },
            )
            self.stdout.write(("Créée : " if created else "Mise à jour : ") + obj.nom_piece)

        self.stdout.write(self.style.SUCCESS("\nSeed terminé ✅"))
