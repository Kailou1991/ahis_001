from Foyer.models import Foyer
from datetime import date

def generer_foyer_depuis_deplacement(deplacement):
    if not deplacement.maladie_suspectee:
        return None

    foyer = Foyer.objects.create(
        date_rapportage=date.today(),
        maladie=deplacement.maladie_suspectee,
        espece=deplacement.espece,
        region=deplacement.region_destination,
        departement=deplacement.departement_destination,
        commune=deplacement.commune_destination,
        localite=deplacement.etablissement_destination or "Non renseigné",
        nbre_sujets_malade=deplacement.nombre_animaux_malades or 0,
        nbre_sujets_traite=deplacement.nombre_animaux_traites or 0,
        nbre_sujets_vaccines=deplacement.nombre_animaux_vaccines or 0,
        nbre_sujets_en_quarintaines=deplacement.nombre_animaux_quarantaine or 0,
        mesure_controle=deplacement.mesures_prises or "RAS",
        source_signalement="Déplacement",
        remarque="Foyer généré automatiquement depuis un déplacement"
    )
    return foyer
