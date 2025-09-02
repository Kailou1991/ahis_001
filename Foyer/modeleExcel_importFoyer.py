import pandas as pd
import os

# Créez un DataFrame avec les colonnes requises
data = {
    'date_rapportage': [],
    'maladie': [],
    'region': [],
    'departement': [],
    'commune': [],
    'localite': [],
    'lieu_suspicion': [],
    'nom_lieu_suspicion': [],
    'longitude': [],
    'latitude': [],
    'effectif_troupeau': [],
    'nbre_sujets_malade': [],
    'nbre_sujets_morts': [],
    'nbre_sujets_traites': [],
    'nbre_sujets_vaccines': [],
    'nbre_sujets_en_quarantaine': [],
    'nbre_sujets_abattus': [],
    'nbre_humains_atteints': [],
    'mesure_controle': [],
    'prelevement_envoye': [],
    'date_envoi_prelevement': [],
    'nature_prelevement': [],
    'nbre_echantillon_prev': [],
    'vaccinations_recentes': [],
    'maladie_vaccination': [],
    'date_vaccination': [],
    'resultat_laboratoire': [],
    'date_reception_prelevement': [],
    'date_resultat': [],
    'nbre_echant_recu': [],
    'nbre_echant_positif': [],
    'nbre_echant_inexploitable': [],
    'laboratoire': [],
    'type_test_labo': [],
    'recommandations': []
}

df = pd.DataFrame(data)

# Définir le chemin du fichier dans le répertoire statique
static_dir = 'myapp/static/files'
os.makedirs(static_dir, exist_ok=True)
file_path = os.path.join(static_dir, 'foyer_import_template_with_instructions.xlsx')

# Sauvegardez le DataFrame dans un fichier Excel
df.to_excel(file_path, index=False, engine='openpyxl')

print(f'Fichier Excel généré : {file_path}')
