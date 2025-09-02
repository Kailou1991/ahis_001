import io
import base64
import calendar
import numpy as np
import matplotlib.pyplot as plt
import pandas as pd
from datetime import datetime
from django.shortcuts import render
from django.db.models import Count, Sum
from aibd.models import ServiceVeterinaireAIBD, Continent, PaysMonde


def generate_bar_chart(labels, values, label1, label2, title):
    fig, ax = plt.subplots()
    ax.bar(labels, values, color=['#4E79A7', '#F28E2B'])
    ax.set_title(title)
    ax.set_ylabel(label1)
    ax.set_xlabel(label2)
    plt.xticks(rotation=45)

    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    graphic = base64.b64encode(image_png).decode('utf-8')
    plt.close(fig)
    return graphic


def generate_pie_chart(labels, sizes):
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax.axis('equal')
    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_png = buffer.getvalue()
    buffer.close()
    graphic = base64.b64encode(image_png).decode('utf-8')
    plt.close(fig)
    return graphic


def dashboard_aibd(request):
    data = ServiceVeterinaireAIBD.objects.all()

    # Filtres
    continent_id = request.GET.get('continent')
    pays_id = request.GET.get('pays')
    type_operation = request.GET.get('type_operation')
    type_produit = request.GET.get('type_produit')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')

    if continent_id:
        data = data.filter(continent_id=continent_id)
    if pays_id:
        data = data.filter(pays_id=pays_id)
    if type_operation:
        data = data.filter(type_operation=type_operation)
    if type_produit:
        data = data.filter(type_produit=type_produit)
    if date_debut and date_fin:
        data = data.filter(date__range=[date_debut, date_fin])

    # KPIs
    total_ops = data.count()
    total_imports = data.filter(type_operation='importation').count()
    total_exports = data.filter(type_operation='exportation').count()
    total_animaux = data.filter(type_produit='Animaux').count()
    quantite_pod = data.filter(type_produit='POD').aggregate(Sum('quantite'))['quantite__sum'] or 0
    nb_medicaments = data.filter(type_produit='Medicaments').count()
    vols_uniques = data.values('numero_vol').distinct().count()
    pays_uniques = data.values('pays').distinct().count()

    # Graphique 1 : évolution mensuelle (groupé)
    df = pd.DataFrame(data.values('date', 'type_operation'))
    if not df.empty:
        df['mois'] = pd.to_datetime(df['date']).dt.month
        evolution = df.groupby(['mois', 'type_operation']).size().unstack(fill_value=0)
        mois_labels = [calendar.month_abbr[m] for m in evolution.index]
        x = np.arange(len(mois_labels))
        width = 0.35

        import_values = evolution.get('importation', pd.Series([0]*len(x)))
        export_values = evolution.get('exportation', pd.Series([0]*len(x)))

        fig, ax = plt.subplots()
        ax.bar(x - width / 2, import_values, width, label='Importations')
        ax.bar(x + width / 2, export_values, width, label='Exportations')
        ax.set_title("Évolution des opérations")
        ax.set_ylabel("Nombre")
        ax.set_xlabel("Mois")
        ax.set_xticks(x)
        ax.set_xticklabels(mois_labels)
        ax.legend()

        buffer = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buffer, format='png')
        buffer.seek(0)
        evolution_chart = base64.b64encode(buffer.getvalue()).decode('utf-8')
        buffer.close()
        plt.close(fig)
    else:
        evolution_chart = None

    # Graphique 2 : répartition type produit
    repartition = data.values('type_produit').annotate(count=Count('id'))
    pie_labels = [r['type_produit'] for r in repartition]
    pie_sizes = [r['count'] for r in repartition]
    pie_chart = generate_pie_chart(pie_labels, pie_sizes) if pie_sizes else None

    # Graphique 3 : top 10 produits
    top_produits_qs = data.values('produit').annotate(qte=Sum('quantite')).order_by('-qte')[:10]
    top_labels = [p['produit'] for p in top_produits_qs]
    top_values = [p['qte'] for p in top_produits_qs]
    top_chart = generate_bar_chart(top_labels, top_values, 'Quantité', 'Produit', 'Top 10 produits') if top_labels else None

    context = {
        'total_ops': total_ops,
        'total_imports': total_imports,
        'total_exports': total_exports,
        'total_animaux': total_animaux,
        'quantite_pod': quantite_pod,
        'nb_medicaments': nb_medicaments,
        'vols_uniques': vols_uniques,
        'pays_uniques': pays_uniques,
        'evolution_chart': evolution_chart,
        'pie_chart': pie_chart,
        'top_chart': top_chart,
        'data_recent': data.order_by('-date')[:10],
        'continents': Continent.objects.all(),
        'pays': PaysMonde.objects.all(),
    }

    return render(request, 'aibd/dashboard_aibd.html', context)
