# views.py
from django.shortcuts import render
from django.db.models import Count, Q, Avg, F, FloatField, ExpressionWrapper, Case, When, Value
from inspection_medicaments.models import (
    InspectionEtablissement, StructureVente, VerificationPhysiqueProduits,
    ControleDocumentaireDetaillant, ConditionsDelivrance,
    GestionDechetsBiomedicaux, OperationsDistribution
)
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune
from django import forms
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import pandas as pd
from django.http import HttpResponse
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.decorators import login_required



class InspectionFilterForm(forms.Form):
    region = forms.ModelChoiceField(queryset=Region.objects.all(), required=False, label="Région")
    departement = forms.ModelChoiceField(queryset=Departement.objects.all(), required=False, label="Département")
    commune = forms.ModelChoiceField(queryset=Commune.objects.all(), required=False, label="Commune")
    annee = forms.ChoiceField(choices=[], required=False, label="Année")
    type_structure = forms.ChoiceField(
        choices=[('', 'Tous'), ('GROSSISTE', 'Grossiste'), ('Detaillant', 'Détaillant')],
        required=False, label="Type de structure"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        annees = InspectionEtablissement.objects.dates('date', 'year')
        self.fields['annee'].choices = [(a.year, a.year) for a in annees]

        # Appliquer la classe form-control à tous les champs
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


def generate_base64_plot(x, y, kind='bar', title='', xlabel='', ylabel=''):
    x = x.astype(str)  # S'assurer que les années sont des chaînes
    fig, ax = plt.subplots(figsize=(6, 4))

    if kind == 'bar':
        bars = ax.bar(x, y, color=plt.cm.tab20.colors[:len(x)])  # Couleurs différentes
        for bar in bars:
            height = bar.get_height()
            ax.annotate(f'{int(height)}', xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 3), textcoords="offset points",
                        ha='center', va='bottom', fontsize=9)
        ax.set_xlabel(xlabel)
        ax.set_xticklabels(x, rotation=45)
        ax.set_yticks([])  # Supprimer l'axe Y
        ax.set_ylabel('')
    elif kind == 'pie':
        ax.pie(y, labels=x, autopct='%1.1f%%')

    ax.set_title(title)
    fig.tight_layout()
    buffer = BytesIO()
    plt.savefig(buffer, format='png')
    plt.close(fig)
    buffer.seek(0)
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('utf-8')



@login_required
def dashboard_inspections(request):
    form = InspectionFilterForm(request.GET or None)
    inspections = InspectionEtablissement.objects.select_related('structure')

    if form.is_valid():
        cd = form.cleaned_data
        if cd['region']:
            inspections = inspections.filter(structure__region=cd['region'])
        if cd['departement']:
            inspections = inspections.filter(structure__departement=cd['departement'])
        if cd['commune']:
            inspections = inspections.filter(structure__commune=cd['commune'])
        if cd['annee']:
            inspections = inspections.filter(date__year=cd['annee'])
        if cd['type_structure']:
            inspections = inspections.filter(structure__type_structure=cd['type_structure'])

    inspection_ids = inspections.values_list('id', flat=True)
    total = inspections.count()
    grossistes = inspections.filter(structure__type_structure='GROSSISTE').count()
    detaillants = inspections.filter(structure__type_structure='Detaillant').count()

    autorisation_total = ControleDocumentaireDetaillant.objects.filter(inspection_id__in=inspection_ids).count()
    autorisation_oui = ControleDocumentaireDetaillant.objects.filter(inspection_id__in=inspection_ids, autorisation_exercer='oui').count()
    taux_autorisation = (autorisation_oui / autorisation_total * 100) if autorisation_total else 0

    sans_registre = ControleDocumentaireDetaillant.objects.filter(inspection_id__in=inspection_ids, registre_ventes_mv='non').count()
    amm_non = VerificationPhysiqueProduits.objects.filter(inspection_id__in=inspection_ids).filter(Q(amm='non') | Q(date_peremption='non_valide')).count()
    vente_sans_ordonnance = ConditionsDelivrance.objects.filter(inspection_id__in=inspection_ids, vente_mv='sans_ordonnance').count()
    enregistrement_ok = OperationsDistribution.objects.filter(inspection_id__in=inspection_ids, enregistrement_automatique='fait').count()
    non_conforme_transport = OperationsDistribution.objects.filter(inspection_id__in=inspection_ids, respect_transport='non').count()
    moyenne_personnel = ControleDocumentaireDetaillant.objects.filter(inspection_id__in=inspection_ids).aggregate(Avg('nombre_personnel'))['nombre_personnel__avg']

    conformes = autorisation_oui + enregistrement_ok
    total_criteres = autorisation_total + len(inspection_ids)
    score_global = (conformes / total_criteres * 100) if total_criteres else 0

    graph_data = inspections.values('date__year').annotate(nombre=Count('id')).order_by('date__year')
    repartition_structures = inspections.values('structure__type_structure').annotate(nb=Count('id'))
    repartition_dechets = GestionDechetsBiomedicaux.objects.filter(inspection_id__in=inspection_ids).values('type_gestion').annotate(nb=Count('id'))

    # 🔢 Graphiques encodés base64
    df_graph = pd.DataFrame(graph_data)
    df_structures = pd.DataFrame(repartition_structures)
    df_dechets = pd.DataFrame(repartition_dechets)

    url_graph_data = generate_base64_plot(
        x=df_graph['date__year'], y=df_graph['nombre'],
        kind='bar', title="Inspections par année", xlabel="Année", ylabel="Nombre"
    ) if not df_graph.empty else None

    url_repartition_structures = generate_base64_plot(
        x=df_structures['structure__type_structure'], y=df_structures['nb'],
        kind='pie', title="Répartition des structures"
    ) if not df_structures.empty else None

    url_repartition_dechets = generate_base64_plot(
        x=df_dechets['type_gestion'], y=df_dechets['nb'],
        kind='bar', title="Gestion des déchets", xlabel="Type", ylabel="Nombre"
    ) if not df_dechets.empty else None

    region_conformite = Region.objects.annotate(
        total=Count('structurevente__inspectionetablissement', filter=Q(structurevente__inspectionetablissement__in=inspections)),
        conformes=Count('structurevente__inspectionetablissement__controledocumentairedetaillant', filter=Q(structurevente__inspectionetablissement__controledocumentairedetaillant__autorisation_exercer='oui'))
    ).annotate(
        taux=Case(
            When(total=0, then=Value(0.0)),
            default=ExpressionWrapper(F('conformes') * 100.0 / F('total'), output_field=FloatField()),
            output_field=FloatField()
        )
    )

    classement_deps = inspections.values('structure__departement__Nom').annotate(nb=Count('id')).order_by('-nb')

    tableau = inspections.select_related('structure', 'structure__region', 'structure__departement', 'structure__commune')

    context = {
        'form': form,
        'total': total,
        'grossistes': grossistes,
        'detaillants': detaillants,
        'taux_autorisation': round(taux_autorisation, 1),
        'sans_registre': sans_registre,
        'amm_non': amm_non,
        'vente_sans_ordonnance': vente_sans_ordonnance,
        'enregistrement_ok': enregistrement_ok,
        'non_conforme_transport': non_conforme_transport,
        'moyenne_personnel': round(moyenne_personnel or 0, 1),
        'score_global': round(score_global, 1),
        'url_graph_data': url_graph_data,
        'url_repartition_structures': url_repartition_structures,
        'url_repartition_dechets': url_repartition_dechets,
        'region_conformite': region_conformite,
        'classement_deps': classement_deps,
        'tableau': tableau,
    }

    return render(request, 'inspectionMedicaments/dashboard.html', context)



@login_required
def export_inspections_excel(request):
    inspections = InspectionEtablissement.objects.select_related(
        'structure__region', 'structure__departement', 'structure__commune', 'agent'
    )

    data = []

    for i in inspections:
        doc = getattr(i, 'controledocumentairedetaillant', None)
        phy = getattr(i, 'verificationphysiqueproduits', None)
        deliv = getattr(i, 'conditionsdelivrance', None)
        dechet = getattr(i, 'gestiondechetsbiomedicaux', None)
        locaux = getattr(i, 'descriptionlocaux', None)
        distr = getattr(i, 'operationsdistribution', None)

        data.append({
            "Date": i.date,
            "Structure": i.structure.nom,
            "Type de structure": i.structure.type_structure,
            "Région": i.structure.region.Nom if i.structure.region else "",
            "Département": i.structure.departement.Nom if i.structure.departement else "",
            "Commune": i.structure.commune.Nom if i.structure.commune else "",
            "Agent inspecteur": i.agent.nom if i.agent else "",
            "Fonction agent": i.agent.fonction if i.agent else "",
            "Service de rattachement": i.agent.service if i.agent else "",
            "Téléphone agent": i.agent.telephone if i.agent else "",
            "Autorisation d’exercer": doc.autorisation_exercer if doc else "",
            "Nombre de personnel": doc.nombre_personnel if doc else "",
            "Qualification personnel": doc.qualification if doc else "",
            "Sources approvisionnement": doc.sources_approvisionnement if doc else "",
            "Registre de ventes": doc.registre_ventes_mv if doc else "",
            "Enseigne visible": doc.enseigne if doc else "",
            "AMM": phy.amm if phy else "",
            "AMM valide": phy.date_peremption if phy else "",
            "Composition": phy.composition if phy else "",
            "Contenant": phy.contenant if phy else "",
            "Conditionnement": phy.conditionnement if phy else "",
            "Vente de MV": deliv.vente_mv if deliv else "",
            "Vente au détail": deliv.au_detail if deliv else "",
            "Gestion déchets biomédicaux": dechet.type_gestion if dechet else "",
            "Locaux séparés": locaux.separation_locaux if locaux else "",
            "Chambre froide": locaux.chambre_froide if locaux else "",
            "Source énergie": locaux.source_energie if locaux else "",
            "Transport conforme": distr.respect_transport if distr else "",
            "Enregistrement automatique": distr.enregistrement_automatique if distr else "",
            "Respect FEFO": distr.respect_fefo if distr else "",
        })

    df = pd.DataFrame(data)
    buffer = BytesIO()
    df.to_excel(buffer, index=False)
    buffer.seek(0)

    response = HttpResponse(
        buffer,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename="inspections_detaillees.xlsx"'
    return response