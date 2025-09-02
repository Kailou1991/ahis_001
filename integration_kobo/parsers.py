from ChiffreVaccination.models import ChiffreVaccination
from Campagne.models import Campagne
from Maladie.models import Maladie
from Espece.models import Espece
from Foyer.models import Foyer
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune
from ObjectifVaccination.models import ObjectifVaccination
from django.utils.dateparse import parse_date
import pandas as pd
from pathlib import Path
from django.db import transaction
import unicodedata
import re
from inspection_medicaments.models import (
    AgentInspecteur, StructureVente, InspectionEtablissement,
    ControleDocumentaireDetaillant, VerificationPhysiqueProduits,
    ConditionsDelivrance, GestionDechetsBiomedicaux,
    DescriptionLocaux, OperationsDistribution
)
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune
from datetime import datetime
from aibd.models import ServiceVeterinaireAIBD
from aibd.models import Continent
from aibd.models import PaysMonde



REGION_MAPPING = {
    
}



MAPPING_MALADIES = {
        "clavelée": ["clavelee", "clavelée", "clavelee ovine", "clavelée (ovine)", "la clavelée", "la clavelee", "clavelé", "clavele", "clavlée", "la clavelée ovine"],
        "gourme": ["gourme", "gourme equine", "gourme équine", "gourne", "groume", "gourme/grippe équine"],
        "grippe équine": ["grippe équine", "grippe equine"],
        "grippe aviaire": ["grippe aviaire", "intoxication alimentaire ou grippe aviaire", "influenza aviaire faiblement pathogène", "iafp", "iap", "new", "variole aviaire"],
        "ecthyma contagieux": ["ecthyma", "echtyma", "ecthyma contagieuse", "ecthyma contagieux", "ecthyma contagieux ovine", "echtyma contagieuse", "l'ecthyma contagieuse", "ectyma contagieuse"],
        "PPR": ["ppr", "ppb"],
        "peste bovine (pcb)": ["pcb"],
        "fasciolose": ["fasciolose", "fasciolose hépatique", "distomatose", "distamatose", "dystomatose", "distomatose bovine"],
        "trypanosomose": ["trypanosomose", "la trypanosomose", "trypanosomiase", "tryponosomisase", "parasitose et tripanosomiase"],
        "lymphangite épizootique": ["lymphangite épizootie", "lymphangite épizootique", "lynphangite épizootie", "la lynphangite épizootie", "lymphangite épizootique équine"],
        "ténia": ["tenia", "ténia", "teniose  du  mouton", "la monieziose ou teniasis", "monnesiose", "la monnesiose"],
        "entérotoxémie": ["enterotoxemie", "enterotoxemies", "entérotoxémie"],
        "brucellose": ["brucellose"],
        "ehrlichiose": ["erlichiose", "ehrlichiose", "erlichiose ou mycoplasmose"],
        "verrue": ["verue", "la verue"],
        "parasites internes": ["parasites internes", "parasites", "endoparasitisme", "parasitose", "parasitisme", "ras", "parasitoses, poux"],
        "gale": ["gale", "gale, prurit", "gale et prurit", "gale sarcoptique", "gale et labronémose"],
        "bronchite": ["bronchite", "bronchite chronique", "bronchite et pica", "bronchite et conjonctivite"],
        "fièvre aphteuse": ["fièvre aphteuse", "fa","FA"],
        "piétin": ["piétin", "pietin", "affection podale( pietin)"],
        "strongylose": ["strongylose", "strongylose gastro-intestinale", "strongles respiratoires"],
        "oestrose": ["oestrose", "oestrose ovine", "œustrose ovine"],
        "colique": ["colique", "colique poulain"],
        "intoxication alimentaire": ["intoxication alimentaire", "empoisonnement", "empoisonnement aux pesticides"],
        "fièvre catarrhale du mouton": ["fièvre catarrhale du mouton"],
        "mammites": ["mammite"],
        "pasteurellose porcine": ["pasteurellose porcine"],
        "septicémie": ["septicémie", "septicémie hémorragique contagieuse bovine"],
        "théilériose": ["théilériose"],
        "cowdriose": ["cowdriose"],
        "mycoses": ["mycoses", "dermathophylose"],
        "RAGE" : ["RAG"],
        "échinococcose": ["echonococose", "echinococose", "échinococcose"]
    }

def split_espece_maladie(input_str):
    """
    Sépare une chaîne en deux parties : espèce et maladie
    en détectant le passage minuscule → majuscule.
    Convertit les deux en majuscules.
    Exemple : 'OvinsPPR' => ('OVINS', 'PPR')
    """
    if not input_str:
        return ("", "")
    
    for i in range(1, len(input_str)):
        if input_str[i].isupper() and input_str[i-1].islower():
            espece = input_str[:i].upper()
            maladie = input_str[i:].upper()
            if maladie =='PCB':
                maladie="PPCB"
            if maladie =='PPB':
                maladie="PASTEREULOSE"
            if maladie=='TUB':
                maladie="TUBERCULOSE"
            if maladie =='CS':
                maladie="CHARBON SYMPTOMATIQUE"

            return (espece, maladie)

    return (input_str.upper(), "")


def format_region(nom_region):
    if not nom_region:
        return None
    code = nom_region.strip().upper().replace("’", "'")
    return REGION_MAPPING.get(code)



############ inspection des etablissements de vente des medicaments
@transaction.atomic
def parser_inspection(data, formulaire=None):
    try:
        idkobo = data.get("_id")
        print(f"\n📥 Traitement inspection ID KOBO : {idkobo}")

        # 1. Agent Inspecteur
        agent, _ = AgentInspecteur.objects.get_or_create(
            nom=data.get("group_agent/Nom_Agent_inspecteur", "").strip(),
            defaults={
                "fonction": data.get("group_agent/Fonction_Agent", "").strip(),
                "service": data.get("group_agent/Service_de_rattachement_de_l_agent", "").strip(),
                "telephone": data.get("group_agent/Telephone_Agent", "").strip(),
                "idkobo": idkobo,
                "chiffre_kbt": True
            }
        )

        # 2. Localisation
        region_nom = format_region(data.get("group_structure/province", ""))
        if not region_nom:
            return f"⚠️ Région inconnue ou vide → inspection ignorée"

        region, _ = Region.objects.get_or_create(Nom=region_nom)
        departement_nom = data.get("group_structure/departement", "").strip().upper()
        commune_nom = data.get("group_structure/Commune", "").strip().upper()
        departement, _ = Departement.objects.get_or_create(Nom=departement_nom, Region=region)
        commune, _ = Commune.objects.get_or_create(Nom=commune_nom, DepartementID=departement)

        # 3. Structure visitée
        structure, _ = StructureVente.objects.get_or_create(
            nom=data.get("group_structure/NomStructure", "").strip(),
            defaults={
                "type_structure": data.get("group_structure/structure", "").strip(),
                "gps": data.get("group_structure/GPS", "").strip(),
                "region": region,
                "departement": departement,
                "commune": commune,
                "idkobo": idkobo,
                "chiffre_kbt": True
            }
        )

        # 4. Inspection principale
        date_inspection = data.get("DateInspection")
        inspection, _ = InspectionEtablissement.objects.get_or_create(
            idkobo=idkobo,
            defaults={
                "date": date_inspection,
                "agent": agent,
                "structure": structure,
                "observations_generales": "",
                "chiffre_kbt": True
            }
        )

        # 5. Contrôle Documentaire
        if "groupDetaillant/AutorisationExercer" in data:
            ControleDocumentaireDetaillant.objects.get_or_create(
                inspection=inspection,
                defaults={
                    "autorisation_exercer": data.get("groupDetaillant/AutorisationExercer"),
                    "nombre_personnel": data.get("groupDetaillant/Nombre"),
                    "qualification": data.get("groupDetaillant/Qualification", ""),
                    "observations_personnel": data.get("groupDetaillant/Observations_sur_le_personnel", ""),
                    "sources_approvisionnement": data.get("groupDetaillant/Sources_d_approvisio_t_Factures_d_achats", ""),
                    "registre_ventes_mv": data.get("groupDetaillant/Registres_des_ventes_de_MV"),
                    "observations_registres": data.get("groupDetaillant/Observations_sur_Reg_res_des_ventes_de_MV", ""),
                    "enseigne": data.get("groupDetaillant/Enseigne"),
                    "observations_enseigne": data.get("groupDetaillant/Observations_sur_l_enseigne", ""),
                    "idkobo": idkobo,
                    "chiffre_kbt": True
                }
            )

        # 6. Vérification physique
        if "grp_VERIFICATION_PHYSIQUE_DES_/AMM" in data:
            VerificationPhysiqueProduits.objects.get_or_create(
                inspection=inspection,
                defaults={
                    "amm": data.get("grp_VERIFICATION_PHYSIQUE_DES_/AMM"),
                    "observations_amm": data.get("grp_VERIFICATION_PHYSIQUE_DES_/Observations_sur_les_AMM", ""),
                    "date_peremption": data.get("grp_VERIFICATION_PHYSIQUE_DES_/Date_de_p_remption"),
                    "depuis_quand": data.get("grp_VERIFICATION_PHYSIQUE_DES_/Depuis_quand"),
                    "composition": data.get("grp_VERIFICATION_PHYSIQUE_DES_/Composition", ""),
                    "date_ouverture_flacon": data.get("grp_VERIFICATION_PHYSIQUE_DES_/Date_d_ouverture_du_flacon"),
                    "date_ouverture": data.get("grp_VERIFICATION_PHYSIQUE_DES_/Saisir_la_date_d_ouverture"),
                    "contenant": data.get("grp_VERIFICATION_PHYSIQUE_DES_/Contenant", ""),
                    "conditionnement": data.get("grp_VERIFICATION_PHYSIQUE_DES_/Conditionnement", ""),
                    "idkobo": idkobo,
                    "chiffre_kbt": True
                }
            )

        # 7. Conditions de délivrance
        if "grp_CONDITIONS_DE_DELIVRANCE/Vente_de_MV" in data:
            ConditionsDelivrance.objects.get_or_create(
                inspection=inspection,
                defaults={
                    "vente_mv": data.get("grp_CONDITIONS_DE_DELIVRANCE/Vente_de_MV"),
                    "observations_vente": data.get("grp_CONDITIONS_DE_DELIVRANCE/Observations_sur_la_vente_de_MV", ""),
                    "au_detail": data.get("grp_CONDITIONS_DE_DELIVRANCE/Au_detailPetitsRecond"),
                    "observations_detail": data.get("grp_CONDITIONS_DE_DELIVRANCE/Observations_sur_Au_d_tail_ou_par_flacon", ""),
                    "idkobo": idkobo,
                    "chiffre_kbt": True
                }
            )

        # 8. Gestion des déchets
        if "grp_GESTION_DES_DECHETS_BIOMED/Type_de_gestion" in data:
            GestionDechetsBiomedicaux.objects.get_or_create(
                inspection=inspection,
                defaults={
                    "type_gestion": data.get("grp_GESTION_DES_DECHETS_BIOMED/Type_de_gestion"),
                    "autre_type": data.get("grp_GESTION_DES_DECHETS_BIOMED/Autre_type_de_gestion", ""),
                    "observations": data.get("grp_GESTION_DES_DECHETS_BIOMED/Observations_sur_la_gestion_des_d_chets", ""),
                    "idkobo": idkobo,
                    "chiffre_kbt": True
                }
            )

        # 9. Description des locaux
        if "grp_DESCRIPTION_DES_LOCAUX/Separation_des_locaux_bureaux" in data:
            DescriptionLocaux.objects.get_or_create(
                inspection=inspection,
                defaults={
                    "separation_locaux": data.get("grp_DESCRIPTION_DES_LOCAUX/Separation_des_locaux_bureaux"),
                    "quai_debarquement": data.get("grp_DESCRIPTION_DES_LOCAUX/R_ception_quai_de_d_barquement"),
                    "magasins_stockage": data.get("grp_DESCRIPTION_DES_LOCAUX/Magasins_de_stockage_ration_des_commandes"),
                    "zone_stockage_retir": data.get("grp_DESCRIPTION_DES_LOCAUX/Zone_de_stockage_des_et_retir_s_du_march"),
                    "chambre_froide": data.get("grp_DESCRIPTION_DES_LOCAUX/Chambre_froide_avec_oduits_thermolabiles"),
                    "source_energie": data.get("grp_DESCRIPTION_DES_LOCAUX/Existence_d_une_source_denergi"),
                    "vehicule_transport": data.get("grp_DESCRIPTION_DES_LOCAUX/Vehicules_adaptes_pour_le_tran"),
                    "rayonnage": data.get("grp_DESCRIPTION_DES_LOCAUX/Etageres_palettes_et_armoires"),
                    "observations": "",
                    "idkobo": idkobo,
                    "chiffre_kbt": True
                }
            )

        # 10. Opérations de distribution
        if "grp_VERIFICATION_DES_OPERATION/Verification_et_revision_de_la" in data:
            OperationsDistribution.objects.get_or_create(
                inspection=inspection,
                defaults={
                    "verification_liste_clients": data.get("grp_VERIFICATION_DES_OPERATION/Verification_et_revision_de_la"),
                    "respect_fefo": data.get("grp_VERIFICATION_DES_OPERATION/Respect_du_principe_de_FEFO"),
                    "enregistrement_automatique": data.get("grp_VERIFICATION_DES_OPERATION/Enregistrement_automatique"),
                    "respect_transport": data.get("grp_VERIFICATION_DES_OPERATION/Respect_des_exigence_u_cours_du_transport"),
                    "observations": "",
                    "idkobo": idkobo,
                    "chiffre_kbt": True
                }
            )

        return f"✅ Inspection insérée ou mise à jour : {structure.nom} ({date_inspection})"

    except Exception as e:
        return f"🔥 Erreur ID {data.get('_id')} : {e}"


#############################Chiffre de vaccination#########################
def get_or_create_campagne(date_vaccination):
    year = date_vaccination.year
    campagne_name = f"{year}-{year + 1}" if date_vaccination.month >= 10 else f"{year - 1}-{year}"
    campagne, _ = Campagne.objects.get_or_create(Campagne=campagne_name)
    return campagne




from django.db import transaction

def parse_vaccination_data(data, formulaire=None):
    from django.utils.timezone import now
    import os
    import pandas as pd

    messages = []
    rows_vide = []

    try:
        idkobo = data.get("_id")
        print(f"\n📥 Traitement vaccination ID KOBO : {idkobo}")

        date_vaccination = parse_date(data.get("Datesaisie", ""))
        libelle_campagne = data.get("Campagne", "").strip()
        type_campagne = data.get("Type_de_campagne", "").strip().lower()
        print(f"📥 Type_de_campagne : {type_campagne}")
        type_campagne_clean = 'Masse' if 'mass' in type_campagne else 'Ciblee'

        if not libelle_campagne:
            libelle_campagne = f"{date_vaccination.year}"

        campagne, _ = Campagne.objects.get_or_create(
            Campagne=libelle_campagne,
            type_campagne=type_campagne_clean
        )

        region_nom = data.get("Grp4/region", "").strip()
        departement_nom = data.get("Grp4/departement", "").strip().upper()

        if not region_nom:
            print("❗ Région vide – enregistrement sous 'INCONNU'")
            region_nom = "INCONNU"
            rows_vide.append({
                "ID KOBO": idkobo,
                "Date vaccination": str(date_vaccination),
                "Région": region_nom
            })

        region, _ = Region.objects.get_or_create(Nom=region_nom)
        departement, _ = Departement.objects.get_or_create(Nom=departement_nom, Region=region)

        troupeaux = data.get("Grp5", [])
        if isinstance(troupeaux, dict):
            troupeaux = [troupeaux]

        for troupeau in troupeaux:
            with transaction.atomic():
                # 📌 Commune peut être totalement absente dans les campagnes ciblées
                commune_nom = troupeau.get("Grp5/commune")
                if not commune_nom:
                    commune_nom = "INCONNUE"
                    messages.append(f"⚠️ Commune absente (ID {idkobo}) - valeur forcée à 'INCONNUE'")

                commune_nom = commune_nom.strip().upper() if isinstance(commune_nom, str) else "INCONNUE"
                commune, _ = Commune.objects.get_or_create(Nom=commune_nom, DepartementID=departement)

                if type_campagne_clean == "Masse":
                    maladie_raw = troupeau.get("Grp5/maladie_masse", "").strip().upper()
                    effectif_vaccine = int(troupeau.get("Grp5/vaccine_public") or 0) + int(troupeau.get("Grp5/vaccine_prive") or 0)
                    effectif_marque = int(troupeau.get("Grp5/marque_public") or 0) + int(troupeau.get("Grp5/marque_prive") or 0)
                else:
                    maladie_raw = troupeau.get("Grp5/maladie_ciblee", "").strip().upper()
                    effectif_vaccine = int(troupeau.get("Grp5/nbr_animaux_vaccines") or 0)
                    effectif_marque = 0  # Pas de marquage ciblé

                maladie = Maladie.objects.get_or_create(Maladie=maladie_raw or "INCONNUE", defaults={"Type": "Animale"})[0]
                espece = Espece.objects.get_or_create(Espece="Indéfinie")[0]

                if not maladie.Espece.filter(id=espece.id).exists():
                    maladie.Espece.add(espece)

                obj = ChiffreVaccination.objects.filter(
                    idkobo=idkobo,
                    maladie=maladie,
                    espece=espece,
                    commune=commune
                ).first()

                if obj:
                    updated = (
                        str(obj.date_vaccination) != str(date_vaccination) or
                        obj.campagne != campagne or
                        obj.region != region or
                        obj.departement != departement or
                        obj.commune != commune or
                        obj.effectif_vacciné != effectif_vaccine or
                        obj.effectif_marqué != effectif_marque
                    )
                    if updated:
                        obj.date_vaccination = date_vaccination
                        obj.campagne = campagne
                        obj.region = region
                        obj.departement = departement
                        obj.commune = commune
                        obj.effectif_vacciné = effectif_vaccine
                        obj.effectif_marqué = effectif_marque
                        obj.save()
                        messages.append(f"🔄 MAJ vaccination : {maladie.Maladie} - {commune_nom}")
                else:
                    ChiffreVaccination.objects.create(
                        date_vaccination=date_vaccination,
                        campagne=campagne,
                        maladie=maladie,
                        espece=espece,
                        effectif_vacciné=effectif_vaccine,
                        effectif_marqué=effectif_marque,
                        nombre_eleveur=0,
                        region=region,
                        departement=departement,
                        commune=commune,
                        idkobo=idkobo,
                        chiffre_kbt=True
                    )
                    messages.append(f"✅ Vaccination insérée : {maladie.Maladie} - {commune_nom}")

    except Exception as e:
        print(f"🔥 Erreur : {e}")
        messages.append(f"⚠️ Erreur traitement vaccination ID {data.get('_id')}: {e}")

    if rows_vide:
        df = pd.DataFrame(rows_vide)
        timestamp = now().strftime("%Y%m%d_%H%M%S")
        output_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"vaccinations_region_vide_{timestamp}.xlsx")
        df.to_excel(filepath, index=False)
        print(f"📁 Fichier des régions vides : {filepath}")

    return messages


##########################objectif des vaccinnations####################

@transaction.atomic
def parse_objectif_vaccination(data, formulaire=None):
    try:
        id_kobo = data.get("_id")
        print(f"\n📥 Traitement ID Kobo : {id_kobo}")

        annee = data.get("Vaccins/Annee")
        if not annee:
            print(f"⚠️ Année manquante pour ID Kobo {id_kobo}")
            return

        campagne_label = f"{int(annee) - 1}-{annee}"
        campagne, created = Campagne.objects.get_or_create(Campagne=campagne_label)
        print(f"📅 Campagne : {campagne_label} ({'créée' if created else 'existante'})")

        province_brute = data.get("Vaccins/Province", "")
        region_nom = format_region(province_brute)

        if not region_nom:
            print(f"⚠️ Province invalide ou vide pour ID Kobo {id_kobo}")
            return

        region, created = Region.objects.get_or_create(Nom=region_nom)
        print(f"🗺️ Région : {region.Nom} ({'créée' if created else 'existante'})")

        objectifs = [
            {"maladie": "PPR", "especes": ["Ovin"], "champ": "Vaccins/Doses_PPR"},
            {"maladie": "PPCB", "especes": ["Bovin"], "champ": "Vaccins/Doses_PPCB"},
        ]

        for obj in objectifs:
            champ = obj["champ"]
            raw_val = data.get(champ)
            try:
                objectif_val = int(raw_val)
            except (ValueError, TypeError):
                print(f"⚠️ Valeur invalide '{raw_val}' pour {champ}")
                continue

            if objectif_val <= 0:
                print(f"⚠️ Objectif nul ou négatif ({objectif_val}) pour {champ}")
                continue

            maladie, created = Maladie.objects.get_or_create(
                Maladie=obj["maladie"],
                defaults={"Type": "Animale"}
            )
            print(f"{'➕' if created else '✅'} Maladie : {maladie.Maladie}")

            for espece_nom in obj["especes"]:
                espece, created = Espece.objects.get_or_create(Espece=espece_nom)
                print(f"{'➕' if created else '✅'} Espèce : {espece.Espece}")

                if not maladie.Espece.filter(id=espece.id).exists():
                    maladie.Espece.add(espece)
                    print(f"🔗 Lien ajouté : {maladie.Maladie} ↔ {espece.Espece}")

                # Ne pas regrouper par région, chaque campagne = une ligne unique (idkobo comme identifiant)
                ObjectifVaccination.objects.get_or_create(
                    campagne=campagne,
                    espece=espece,
                    maladie=maladie,
                    region=region,
                    objectif=objectif_val,
                    effectif_eligible=objectif_val,
                    idkobo=id_kobo,
                    chiffre_kbt=True
                )
                print(f"✅ Objectif inséré : {maladie.Maladie} - {espece.Espece} - {region.Nom}")

    except Exception as e:
        print(f"🔥 Erreur ID {data.get('_id')} : {e}")

#####################surveillance des maladies####################
foyers_ignores_liste = []

def enregistrer_foyer_ignore_console(idkobo, region, departement, commune, espece, maladie, motif):
    ligne = {
        "ID KOBO": idkobo,
        "Région": region,
        "Département": departement,
        "Commune": commune,
        "Espèce brute": espece,
        "Maladie brute": maladie,
        "Motif": motif
    }
    foyers_ignores_liste.append(ligne)

def afficher_foyers_ignores():
    if foyers_ignores_liste:
        print("\n--- 🛑 Foyers ignorés ---")
        df = pd.DataFrame(foyers_ignores_liste)
        print(df.to_markdown(index=False))
    else:
        print("\n✅ Aucun foyer ignoré.")










@transaction.atomic
def parse_surveillance_data(data, formulaire=None):
    messages = []
    try:
        idkobo = data.get("_id")
        date_rapportage = datetime.strptime(data.get("Grp1/Date_rapportage", "").strip(), "%Y-%m-%d").date()
       
        #print(f"⬹️ Traitement du foyer ID KOBO : {idkobo}")
        print(f"📌 Foyer inséré : ID {idkobo} | Date rapportage = {date_rapportage}")


        # Localisation
        region_nom = data.get("Grp3/region", "").strip().upper()
        departement_nom = data.get("Grp3/departement", "").strip().upper()
        commune_nom = data.get("Grp3/commune", "").strip().upper()

        if not region_nom :
            enregistrer_foyer_ignore_console(idkobo, region_nom, departement_nom, commune_nom, "", "", "Localisation incomplète")
            return [f"Foyer {idkobo} ignoré : Localisation incomplète"]

        region, _ = Region.objects.get_or_create(Nom=region_nom)
        departement, _ = Departement.objects.get_or_create(Nom=departement_nom, Region=region)
        commune, _ = Commune.objects.get_or_create(Nom=commune_nom, DepartementID=departement)

        # Espèce + maladie
        animaux = data.get("Grp6", [])
        if not animaux or not isinstance(animaux, list):
            return [f"Foyer {idkobo} ignoré : Pas de bloc animaux trouvé"]

        bloc = animaux[0]
        code_raw = bloc.get("Grp6/liste_anisensibles", "").strip()
        espece_raw, maladie_raw_2 = split_espece_maladie(code_raw)
        espece_nom = espece_raw
        maladie_nom_2 = maladie_raw_2


        if not espece_nom:
            enregistrer_foyer_ignore_console(idkobo, region_nom, departement_nom, commune_nom, code_raw, "", "Espèce vide")
            return [f"Foyer {idkobo} ignoré : Espèce vide"]

        espece, _ = Espece.objects.get_or_create(Espece=espece_nom)

        # Maladie principale (Grp5)
        maladie_raw = maladie_nom_2
        if maladie_raw == "AUT":
            def mapper_maladie(nom_brut):
                nom = nom_brut.strip().lower()
                for maladie_std, variantes in MAPPING_MALADIES.items():
                    if nom in [v.lower() for v in variantes]:
                        return maladie_std
                return nom_brut.strip().upper()
            maladie_nom = mapper_maladie(data.get("Grp5/autre_maladie_suspectee", ""))
        else:
            maladie_nom = maladie_raw

        if not maladie_nom:
            enregistrer_foyer_ignore_console(idkobo, region_nom, departement_nom, commune_nom, espece_nom, "", "Maladie vide")
            return [f"Foyer {idkobo} ignoré : Maladie vide"]

        maladie, _ = Maladie.objects.get_or_create(Maladie=maladie_nom, defaults={"Type": "Animale"})

        if not maladie.Espece.filter(id=espece.id).exists():
            maladie.Espece.add(espece)

        # Géolocalisation
        coords = data.get("Grp3/Geolocalisation_foyer", "").split()
        try:
            latitude = float(coords[0])
            longitude = float(coords[1])
        except:
            latitude = None
            longitude = None

        # Dates (rapportage et prélèvements)

        date_envoi_prelev = data.get("Grp10/Date_envoi_prelev")
        date_reception_prelev = data.get("Grp11/Date_reception_chantillons")
        date_resultat = data.get("Grp11/Date_resultat")

        # Données animales
        effectif_troupeau = int(bloc.get("Grp6/totaltroupeau", 0))
        total_malade = int(bloc.get("Grp6/total_malade", 0))
        total_mort = int(bloc.get("Grp6/calcul_animaux_morts", 0))

        # Mesures de contrôle
        mesures = data.get("Grp7/MesureCtrl", "")
        mesures_controle = ",".join(mesures.split()) if mesures else ""

        # Champs labo
        prelevement_envoye = data.get("ajouter_un_prelevement", "NON").strip().upper()
        nature_prelevement = data.get("Grp10/Echantillon_prelev", "").strip()
        resultat_laboratoire = data.get("Voulez_vous_ajouter_un_laborat", "NON").strip().upper()

        # Construction des données
        foyer_data = {
            "espece": espece,
            "maladie": maladie,
            "region": region,
            "departement": departement,
            "commune": commune,
            "longitude": longitude,
            "latitude": latitude,
            "effectif_troupeau": effectif_troupeau,
            "nbre_sujets_malade": total_malade,
            "nbre_sujets_morts": total_mort,
            "nbre_sujets_vaccines": int(data.get("Grp7/nbre_d_animaux_vaccin_s", 0)),
            "nbre_sujets_en_quarantaine": int(data.get("Grp7/Nbre_d_animaux_mise_en_quarant", 0)),
            "nbre_sujets_traites": int(data.get("Grp7/Nbre_animaux_traites", 0)),
            "nbre_sujets_abattus": int(data.get("Grp7/nbre_d_animaux_abattus", 0)),
            "nbre_echant_recu": 0,
            "nbre_echant_inexploitable": 0,
            "nbre_echant_positif": 0,
            "mesure_controle": mesures_controle,
            "nature_prelevement": nature_prelevement,
            "date_envoi_prelevement": date_envoi_prelev,
            "date_reception_prelevement": date_reception_prelev,
            "date_resultat": date_resultat,
            "resultat_laboratoire": resultat_laboratoire,
            "prelevement_envoye": prelevement_envoye,
        }

        foyer = Foyer.objects.filter(idkobo=idkobo).first()
        if foyer:
            for k, v in foyer_data.items():
                setattr(foyer, k, v)
            foyer.date_rapportage = date_rapportage
            foyer.localite = data.get("Grp3/Nom_du_village", "").strip()
            foyer.lieu_suspicion = data.get("Grp3/lieuSuspicion", "ferme_clinique")
            foyer.nom_lieu_suspicion = data.get("Grp3/nom_pv_service", "").strip()
            foyer.save()
            messages.append(f"🔄 Foyer {idkobo} mis à jour.")
        else:
            Foyer.objects.create(
                idkobo=idkobo,
                date_rapportage=date_rapportage,
                localite=data.get("Grp3/Nom_du_village", "").strip(),
                lieu_suspicion=data.get("Grp3/lieuSuspicion", "ferme_clinique"),
                nom_lieu_suspicion=data.get("Grp3/nom_pv_service", "").strip(),
                chiffre_kbt=True,
                **foyer_data
            )
            messages.append(f"✅ Foyer {idkobo} inséré avec succès.")

    except Exception as e:
        print(f"🔥 Erreur foyer {data.get('_id')}: {e}")
        messages.append(f"⚠️ Erreur foyer {data.get('_id')}: {e}")

    return messages




####Service vétérinaire à AIBD

@transaction.atomic
def parse_service_veterinaire_aibd_data(data, formulaire=None):
    messages = []
    try:
        id_kobo = str(data.get("_id"))
        if not id_kobo:
            return ["❌ Donnée sans identifiant Kobo"]

        # Vérifie si une ligne avec ce ID Kobo + produit existe déjà
        if ServiceVeterinaireAIBD.objects.filter(Idkobo=id_kobo).exists():
            return [f"🔁 Donnée déjà insérée pour ID Kobo : {id_kobo}"]

        # Champs principaux (hors produits)
        date_operation = None
        if data.get("Date"):
            try:
                date_operation = datetime.strptime(data["Date"], "%Y-%m-%d").date()
            except:
                pass

        type_operation = data.get("Type_operation", "").lower().strip()
        expediteur = data.get("Informations/Expediteurs", "").strip()
        lta = data.get("Informations/LTA", "").strip() or None
        continent_code = data.get("Informations/Continent", "").strip()
        pays_nom = data.get("Informations/Pays", "").strip().title()
        type_produit = data.get("Informations/Type", "").strip()
        numero_vol = data.get("Informations/Numero_vol", "").strip() or None
        date_vol = data.get("Informations/Date_vol", "").strip()
        observations = data.get("Observations", "").strip() or None
        societe_transit = data.get("Informations/Societe_transit", "").strip() or None

        # Gestion date_vol (format ISO ou vide)
        try:
            date_vol = datetime.strptime(date_vol, "%Y-%m-%d").date()
        except:
            date_vol = None

        # Continent
        continent = None
        if continent_code:
            continent, _ = Continent.objects.get_or_create(code=continent_code.upper(), defaults={"nom": continent_code.upper()})

        # Pays
        pays = None
        if pays_nom:
            pays, _ = PaysMonde.objects.get_or_create(nom=pays_nom, defaults={"code": pays_nom.upper().replace(" ", "_")[:10], "continent": continent})
            if continent and pays.continent != continent:
                pays.continent = continent
                pays.save()

        # Liste des produits
        produits = data.get("Informations/grp_produits", [])
        if not isinstance(produits, list) or len(produits) == 0:
            return [f"⚠️ Aucune donnée produit trouvée pour l'enregistrement ID Kobo : {id_kobo}"]

        for produit_obj in produits:
            nom_produit = produit_obj.get("Informations/grp_produits/Produits", "").strip()
            quantite = produit_obj.get("Informations/grp_produits/Quantite_prod", "").strip()
            if not nom_produit:
                continue

            try:
                quantite_float = float(quantite.replace(",", "."))
            except:
                quantite_float = None

            ServiceVeterinaireAIBD.objects.create(
                date=date_operation,
                type_operation=type_operation,
                expediteur=expediteur,
                lta=lta,
                continent=continent,
                pays=pays,
                type_produit=type_produit,
                produit=nom_produit,
                quantite=quantite_float,
                numero_vol=numero_vol,
                date_vol=date_vol,
                societe_transit=societe_transit,
                observations=observations,
                Idkobo=id_kobo
            )
        messages.append(f"✅ {len(produits)} produit(s) importé(s) pour ID Kobo {id_kobo}")

    except Exception as e:
        messages.append(f"❌ Erreur pour l'enregistrement {data.get('_id')}: {e}")

    return messages
