from django.shortcuts import render
from django.http import HttpResponse
import pandas as pd
import io
from .models import (
    resultatAnimal, ResultatVillage, ResultatCommune,
    ResultatRegion, ResultatNational
)
from django.db.models import Count, Q, F, Avg,Sum
import matplotlib
matplotlib.use('Agg')  # ✅ Utilise un backend non interactif (sans interface graphique)
import matplotlib.pyplot as plt
import base64
from io import BytesIO
from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

@login_required
def upload_excel(request):
    tableau = []
    message = None
    error = None

    # 🔁 Génération du tableau par type_enquete
    types_enquete = ResultatNational.objects.values_list('type_enquete', flat=True).distinct()
    for type_enquete in types_enquete:
        national = ResultatNational.objects.filter(type_enquete=type_enquete).first()
        prevalence_nationale = (national.taux_prevalence_nationale)*100 if national else None

        # ✅ Filtrage des animaux valides par type d’enquête
        animaux = resultatAnimal.objects.filter(type_enquete=type_enquete)

        vaccinés = animaux.filter(vaccine=True)
        vaccinés_total = vaccinés.count()
        vaccinés_positifs = vaccinés.filter(statut='Positif').count()
        taux_vaccines = (vaccinés_positifs / vaccinés_total) * 100 if vaccinés_total > 0 else 0

        non_vaccinés = animaux.filter(vaccine=False)
        non_vaccinés_total = non_vaccinés.count()
        non_vaccinés_positifs = non_vaccinés.filter(statut='Positif').count()
        taux_non_vaccines = (non_vaccinés_positifs / non_vaccinés_total) * 100 if non_vaccinés_total > 0 else 0

        # ✅ Indice d'efficacité vaccinale (optionnel)
        try:
            indice_efficacite = round(taux_vaccines - taux_non_vaccines, 2)
        except:
            indice_efficacite = 'N/A'

        tableau.append({
            'type_sero': type_enquete,
            'prevalence_nationale': round(prevalence_nationale, 2) if prevalence_nationale is not None else 'N/A',
            'taux_seroconversion_vaccines': round(taux_vaccines, 2),
            'taux_seroconversion_non_vaccines': round(taux_non_vaccines, 2),
            'indice_efficacite': indice_efficacite
        })

    # 🔄 Si POST, traitement du fichier Excel
    if request.method == 'POST' and request.FILES.get('file'):
        try:
            xls = pd.ExcelFile(request.FILES['file'])
            expected_sheets = [
                'resultatAnimal', 'resultatVillage',
                'resultatCommune', 'resultatRegion', 'resultatNational'
            ]
            missing = [s for s in expected_sheets if s not in xls.sheet_names]
            if missing:
                error = f"Feuilles manquantes : {', '.join(missing)}"
            else:
                def clean_bool(val):
                    return str(val).strip().lower() == 'oui'

                def process_resultatAnimal(df):
                    for _, row in df.iterrows():
                        resultatAnimal.objects.create(
                            maladie=row['Maladie'],
                            region=row['region'],
                            commune=row['Commune'],
                            village=row['Village'],
                            numero_animal_preleve=row['Num_animal'],
                            espece_prelevee=row['Espece'],
                            race=row['Race'],
                            sexe=row['Sexe'],
                            classe_age=row['age'],
                            vaccine=clean_bool(row['Vacciné']),
                            marque=clean_bool(row['Marqué']),
                            resultat_labo=row['Resultat'],
                            densite_optique=row['DO'],
                            statut=row['Statut'],
                            type_enquete=row['type_enquete'],
                        )

                def process_resultatVillage(df):
                    for _, row in df.iterrows():
                        ResultatVillage.objects.create(
                            type_enquete=row['type_enquete'],
                            region=row['region'],
                            commune=row['commune'],
                            village=row['village'],
                            positif=row['Positif'],
                            negatif=row['Négatif'],
                            douteux=row['Douteux'],
                            effectif_preleve_valable=row['Effectif prelevé Valable'],
                            prob=row['Prob']
                        )

                def process_resultatCommune(df):
                    for _, row in df.iterrows():
                        ResultatCommune.objects.create(
                            type_enquete=row['type_enquete'],
                            region=row['region'],
                            commune=row['commune'],
                            somme_prob_village=row['SommeProbVillage'],
                            nb_total_village_com=row['NbTotalVillageCom'],
                            nb_village_echan_com=row['NbVillageEchanCom'],
                            prob_commune=row['ProbCommune']
                        )

                def process_resultatRegion(df):
                    for _, row in df.iterrows():
                        ResultatRegion.objects.create(
                            type_enquete=row['type_enquete'],
                            region=row['region'],
                            nb_com_ech=row['NbComEch'],
                            nb_com_region=row['NbComRegion'],
                            somme_prob_commune_par_region=row['SommeProbCommuneParRegion'],
                            proportion_poids_region_pays=row['ProportionPoidsRegion/pays'],
                            ponderation_prevalence_relative=row['Ponderation(ou prevalence Relative)'],
                            variance_relative=row['variance Relative'],
                            prevalence_estimee=row['PrevalenceEstimée']
                        )

                def process_resultatNational(df):
                    for _, row in df.iterrows():
                        ResultatNational.objects.create(
                            type_enquete=row['type_enquete'],
                            taux_prevalence_nationale=row['Taux de prevalence nationale'],
                            erreur_standard=row['ErreurStandard'],
                            intervalle_confiance_inferieur=row['Intervalle confiance inferieur'],
                            intervalle_confiance_superieur=row['Intervalle confiance Superieur']
                        )

                # Exécution des imports
                processors = {
                    'resultatAnimal': process_resultatAnimal,
                    'resultatVillage': process_resultatVillage,
                    'resultatCommune': process_resultatCommune,
                    'resultatRegion': process_resultatRegion,
                    'resultatNational': process_resultatNational,
                }

                for sheet in expected_sheets:
                    processors[sheet](xls.parse(sheet))

                message = "Données importées avec succès."
                return redirect('upload_excel')

        except Exception as e:
            error = f"Erreur lors de l'importation : {str(e)}"

    return render(request, 'sero/uploadPPR.html', {
        'tableau': tableau,
        'message': message,
        'error': error
    })


def generer_fichier_modele(request):
    data = {
        'resultatAnimal': pd.DataFrame(columns=[
            'Maladie', 'region', 'Commune', 'Village', 'Num_animal',
            'Espece', 'Race', 'Sexe', 'age', 'Vacciné',
            'Marqué', 'Resultat', 'DO', 'Statut', 'type_enquete'
        ]),
        'resultatVillage': pd.DataFrame(columns=[
            'type_enquete', 'region', 'commune', 'village',
            'Positif', 'Négatif', 'Douteux',
            'Effectif prelevé Valable', 'Prob'
        ]),
        'resultatCommune': pd.DataFrame(columns=[
            'type_enquete', 'region', 'commune',
            'SommeProbVillage', 'NbTotalVillageCom',
            'NbVillageEchanCom', 'ProbCommune'
        ]),
        'resultatRegion': pd.DataFrame(columns=[
            'type_enquete', 'region', 'NbComEch', 'NbComRegion',
            'SommeProbCommuneParRegion', 'ProportionPoidsRegion/pays',
            'Ponderation(ou prevalence Relative)', 'variance Relative', 'PrevalenceEstimée'
        ]),
        'resultatNational': pd.DataFrame(columns=[
            'type_enquete', 'Taux de prevalence nationale',
            'ErreurStandard', 'Intervalle confiance inferieur',
            'Intervalle confiance Superieur'
        ])
    }

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet, df in data.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

    output.seek(0)
    response = HttpResponse(
        output,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="modele_resultats_seromonitoring.xlsx"'
    return response


def plot_to_base64(fig):
    buf = io.BytesIO()
    fig.tight_layout()
    fig.savefig(buf, format='png')
    buf.seek(0)
    image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    plt.close(fig)
    return image_base64




def dashboard_sero(request):
    type_enquete_disponibles = resultatAnimal.objects.values_list('type_enquete', flat=True).distinct()
    type_enquete = request.GET.get('type_enquete', 'T0')  # par défaut T0

    # Données filtrées
    animaux = resultatAnimal.objects.filter(type_enquete=type_enquete)
    communes = ResultatCommune.objects.filter(type_enquete=type_enquete)
    national = ResultatNational.objects.filter(type_enquete=type_enquete).first()

    # 1. Graphique par région
    regions = ResultatRegion.objects.filter(type_enquete=type_enquete).values('region').annotate(
        prob=Avg('prevalence_estimee') * 100
    )
    region_labels = [r['region'] for r in regions]
    region_vals = [round(r['prob'], 2) if r['prob'] else 0 for r in regions]
    fig1, ax1 = plt.subplots(figsize=(10, 5))
    bars = ax1.bar(region_labels, region_vals)
    for i, bar in enumerate(bars):
        bar.set_color(plt.cm.tab20(i % 20))  # couleurs variées
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height(), f"{bar.get_height():.1f}%", ha='center', va='bottom')
    ax1.set_title('Probabilité moyenne de protection par région')
    ax1.tick_params(axis='x', rotation=45)
    graph_region = plot_to_base64(fig1)

    # 2. Camembert protégées / risque
    total_com = communes.count()
    n_protegees = communes.filter(prob_commune__gte=0.70).count()
    n_risque = total_com - n_protegees
    graph_pie = None
    if total_com > 0:
        fig2, ax2 = plt.subplots()
        ax2.pie([n_protegees, n_risque], labels=["Protégées", "À risque"],
                autopct='%1.1f%%', colors=['green', 'red'])
        ax2.set_title("Répartition des communes")
        graph_pie = plot_to_base64(fig2)

    # 3. Communes séroconversion vaccinée ≥ 70%
    communes_stats = animaux.filter(vaccine=True).values('region', 'commune').annotate(
        total=Count('id'),
        positifs=Count('id', filter=Q(statut='Positif'))
    )
    communes_conv = sum(1 for c in communes_stats if c['total'] > 0 and (c['positifs']/c['total']) * 100 >= 70)

    # 4. Liste communes protégées
    tableau_communes = [
        {
            'commune': c['commune'],
            'region': c['region'],
            'probabilite': round(c['prob_commune'] * 100, 2)
        } for c in communes.filter(prob_commune__gte=0.70).values('commune', 'region', 'prob_commune')
    ]

    # 5. Graphe efficacité par sexe
    base = animaux.values('sexe').annotate(
        total_v=Count('id', filter=Q(vaccine=True)),
        pos_v=Count('id', filter=Q(vaccine=True, statut='Positif')),
        total_nv=Count('id', filter=Q(vaccine=False)),
        pos_nv=Count('id', filter=Q(vaccine=False, statut='Positif')),
    )
    sexe_labels, sexe_eff = [], []
    for row in base:
        taux_v = (row['pos_v'] / row['total_v']) * 100 if row['total_v'] else 0
        taux_nv = (row['pos_nv'] / row['total_nv']) * 100 if row['total_nv'] else 0
        efficacite = taux_v - taux_nv
        sexe_labels.append(row['sexe'])
        sexe_eff.append(round(efficacite, 2))
    fig3, ax3 = plt.subplots()
    bars = ax3.bar(sexe_labels, sexe_eff, color='orange')
    ax3.set_title("Indice d'efficacité de la vaccination par sexe")
    ax3.set_ylabel("Indice d'efficacité (%)")
    for bar in bars:
        height = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width()/2, height, f"{height:.1f}%", ha='center', va='bottom')
    graph_eff_sexe = plot_to_base64(fig3)

    # 🔢 Statistiques globales
    total_animaux = animaux.count()
    n_pos = animaux.filter(statut='Positif').count()
    n_neg = animaux.filter(statut='Negatif').count()
    n_douteux = animaux.filter(statut='Douteux').count()

    vac = animaux.filter(vaccine=True)
    non_vac = animaux.filter(vaccine=False)

    taux_vac = round(vac.filter(statut='Positif').count() / vac.count() * 100, 2) if vac.count() else 0
    taux_non_vac = round(non_vac.filter(statut='Positif').count() / non_vac.count() * 100, 2) if non_vac.count() else 0
    prevalence_nationale = round(national.taux_prevalence_nationale * 100, 2) if national else 'N/A'

    # ✅ Nombre de communes enquêtées pour le type_enquete à partir de ResultatRegion
    nb_communes_total = ResultatRegion.objects.filter(type_enquete=type_enquete).aggregate(
        total=Sum('nb_com_ech')
    )['total'] or 0

    return render(request, 'sero/analyse_epidemiologique.html', {
        'graph_region': graph_region,
        'graph_pie': graph_pie,
        'graph_eff_sexe': graph_eff_sexe,
        'communes_conv': communes_conv,
        'tableau_communes': tableau_communes,
        'type_enquete_disponibles': type_enquete_disponibles,
        'type_enquete': type_enquete,
        'total_animaux': total_animaux,
        'n_pos': n_pos,
        'n_neg': n_neg,
        'n_douteux': n_douteux,
        'nb_communes': total_com,
        'nb_communes_protegees': n_protegees,
        'nb_communes_total': nb_communes_total,
        'taux_vac': taux_vac,
        'taux_non_vac': taux_non_vac,
        'prevalence_nationale': prevalence_nationale,
    })



def supprimer_enquete(request):
    type_enquete_cible = request.GET.get('type_enquete')

    # ✅ Suppression des données si type_enquete valide
    if type_enquete_cible:
        resultatAnimal.objects.filter(type_enquete=type_enquete_cible).delete()
        ResultatVillage.objects.filter(type_enquete=type_enquete_cible).delete()
        ResultatCommune.objects.filter(type_enquete=type_enquete_cible).delete()
        ResultatRegion.objects.filter(type_enquete=type_enquete_cible).delete()
        ResultatNational.objects.filter(type_enquete=type_enquete_cible).delete()
        
        messages.success(request, f"Les données de l'enquête {type_enquete_cible} ont été supprimées avec succès.")
        return redirect('upload_excel')  # Remplace par le nom de ton URL vers le template

    # 🔁 Génération du tableau à afficher (si pas de suppression)
    tableau = []
    types_enquete = ResultatNational.objects.values_list('type_enquete', flat=True).distinct()

    for type_enquete in types_enquete:
        national = ResultatNational.objects.filter(type_enquete=type_enquete).first()
        prevalence_nationale = (national.taux_prevalence_nationale * 100) if national else None

        animaux = resultatAnimal.objects.filter(type_enquete=type_enquete)

        vaccinés = animaux.filter(vaccine=True)
        total_vaccinés = vaccinés.count()
        pos_vaccinés = vaccinés.filter(statut='Positif').count()
        taux_vaccinés = (pos_vaccinés / total_vaccinés) * 100 if total_vaccinés > 0 else 0

        non_vaccinés = animaux.filter(vaccine=False)
        total_non_vaccinés = non_vaccinés.count()
        pos_non_vaccinés = non_vaccinés.filter(statut='Positif').count()
        taux_non_vaccinés = (pos_non_vaccinés / total_non_vaccinés) * 100 if total_non_vaccinés > 0 else 0

        try:
            indice_efficacite = round(taux_vaccinés - taux_non_vaccinés, 2)
        except:
            indice_efficacite = 'N/A'

        tableau.append({
            'type_sero': type_enquete,
            'prevalence_nationale': round(prevalence_nationale, 2) if prevalence_nationale is not None else 'N/A',
            'taux_seroconversion_vaccines': round(taux_vaccinés, 2),
            'taux_seroconversion_non_vaccines': round(taux_non_vaccinés, 2),
            'indice_efficacite': indice_efficacite
        })

    return render(request, 'sero/uploadPPR.html', {
        'tableau': tableau,
    })