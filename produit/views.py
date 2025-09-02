from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from .models import Produit
from .form import ProduitForm,EnregistrementForm
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from django.db.models import Sum, F
from io import BytesIO
import base64
from django.contrib.auth.decorators import login_required
from data_initialization.decorators import group_required
from datetime import datetime
from django.http import JsonResponse
from .models import Produit,Enregistrement
from django.shortcuts import render, redirect
from django.http import JsonResponse
from .form import PartenaireForm, StructureForm 
import matplotlib.pyplot as plt
import pandas as pd
import io
import base64
from django.shortcuts import render
from django.db.models import Sum, Count
from .models import Produit, Enregistrement, Partenaire, Structure
from django.db.models import Sum, Count
from django.db.models.functions import ExtractYear
from django.db.models import Q
import numpy as np
from scipy.interpolate import make_interp_spline
from django.core.files.storage import FileSystemStorage
import openpyxl
from django.http import HttpResponse
import io
import urllib, base64
import folium



@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires','Gestionnaire des Médicaments')
def produit_list(request):
    produits = Enregistrement.objects.all()
  
    return render(request, 'produit/list.html', {'produits': produits})

@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires','Gestionnaire des Médicaments')
def produit_detail(request, pk):
    produit = get_object_or_404(Enregistrement, pk=pk)

    return render(request, 'produit/detail.html', {'produit': produit})


@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments')
def enregistrement_create(request):
    produits = Produit.objects.all()
    if request.method == "POST":
        form = EnregistrementForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Enregistrement créé avec succès.")
            return redirect('produit_list')
        else:
            messages.error(request, "Erreur lors de la création de l'enregistrement. Veuillez vérifier les champs.")
    else:
        form = EnregistrementForm()
        formModalProd=ProduitForm()
        structureForm=StructureForm()
        partenaireForm=PartenaireForm()
    return render(request, 'produit/form.html', {'form': form,'formModalProd':formModalProd, 'produits': produits,'structureForm':structureForm,'partenaireForm':partenaireForm})




@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments')
def produit_update(request, pk):
    enregistrement = get_object_or_404(Enregistrement, pk=pk)
    
    # Récupérer l'ID du produit lié à l'enregistrement
    produit_id = Enregistrement.objects.filter(id=pk).values_list('produit', flat=True).first()
    
    # Vérifier si le produit existe
    produits = Produit.objects.filter(id=produit_id) if produit_id else Produit.objects.none()

    if request.method == "POST":
        form = EnregistrementForm(request.POST, instance=enregistrement)
        if form.is_valid():
            form.save()
            messages.success(request, "Enregistrement mis à jour avec succès.")
            return redirect('produit_list')  # Suppression du `pk` si non nécessaire
    else:
        form = EnregistrementForm(instance=enregistrement)
        formModalProd=ProduitForm()
        structureForm=StructureForm()
        partenaireForm=PartenaireForm()
    return render(request, 'produit/form.html', {'form': form,'formModalProd':formModalProd, 'produits': produits,'structureForm':structureForm,'partenaireForm':partenaireForm})


@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments')
def produit_delete(request, pk):
    produit = get_object_or_404(Enregistrement, pk=pk)
    if request.method == "POST":
        produit.delete()
        messages.success(request, "Enregistrement supprimé avec succès.")
        return redirect('produit_list')
    return render(request, 'produit/confirm_delete.html', {'produit': produit})

################Vues pour la gestions des produits#####################


@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires','Gestionnaire des Médicaments')
def produitVet_list(request):
    produits = Produit.objects.all()
  
    return render(request, 'produit/produit_list.html', {'produits': produits})

@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def produitVet_detail(request, pk):
    produit = get_object_or_404(Produit, pk=pk)

    return render(request, 'produit/produit_detail.html', {'produit': produit})

@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def produitVet_create(request):
    if request.method == "POST":
        form = ProduitForm(request.POST)
        if form.is_valid():
            produit = form.save(commit=False)
            produit.user = request.user
            produit.save()
            messages.success(request, "✅ Produit enregistré avec succès.")
            return redirect('produitVet_list')
        else:
            print("🛑 Erreurs du formulaire :", form.errors)  # ← Voir les vraies erreurs
            messages.error(request, "❌ Erreur : formulaire invalide.")
    else:
        form = ProduitForm()

    return render(request, 'produit/produit_form.html', {'form': form})

@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def produitVet_update(request, pk):
    enregistrement = get_object_or_404(Produit, pk=pk)
    if request.method == "POST":
        form = ProduitForm(request.POST, instance=enregistrement)
        if form.is_valid():
            sauvegarde = form.save(commit=False)
            sauvegarde.user = request.user
            sauvegarde.save()
            messages.success(request, "Enregistrement mis à jour avec succès.")
            return redirect('produitVet_list')  # Suppression du `pk` si non nécessaire
    else:
        form = ProduitForm(instance=enregistrement)
        
    return render(request, 'produit/produit_form.html', {'form': form})

@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def produitVet_delete(request, pk):
    produit = get_object_or_404(Produit, pk=pk)
    if request.method == "POST":
        produit.delete()
        messages.success(request, "Enregistrement supprimé avec succès.")
        return redirect('produitVet_list')
    return render(request, 'produit/produit_confirm_delete.html', {'produit': produit})




@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def export_produitsVet_excel(request):
    # Créer un classeur Excel
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = 'Produits'

    # Écrire les en-têtes de colonne
    headers = ['Type du produit','Nom du Produit', 'Classe Thérapeutique', 'Familles Antibiotiques', 'Forme Pharmaceutique', 'Substances Actives', 'Numéro Autorisation AMM', 'Date de Délivrance AMM', 'Numéro Décision AMM', 'Status AMM']
    sheet.append(headers)

    # Récupérer les produits et écrire les lignes dans le fichier Excel
    produits = Produit.objects.all()
    for produit in produits:
        if produit.type_produit!='MEDICAMENT':
            AMM=None
        else:
            AMM=produit.status_AMM

        sheet.append([
            produit.type_produit,
            produit.nom_du_produit,
            produit.classe_therapeutique,
            produit.familles_antibiotiques,
            produit.forme_pharmaceutique,
            produit.substances_actives,
            produit.numero_autorisation_AMM,
            produit.date_delivrance_AMM.strftime('%d/%m/%Y') if produit.date_delivrance_AMM else '',
            produit.numero_decision_AMM,
            AMM
            
        ])

    # Créer la réponse HTTP avec le type de contenu Excel
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="produits.xlsx"'
    workbook.save(response)
    return response

##################Fonctions particulieres##############
@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def get_produit_details(request, produit_id):
    produit = get_object_or_404(Produit, id=produit_id)
    data = {
        'nom_du_produit': produit.nom_du_produit,
        'type_produit': produit.type_produit,
        'classe_therapeutique': produit.classe_therapeutique,
        'familles_antibiotiques': produit.familles_antibiotiques,
        'forme_pharmaceutique': produit.forme_pharmaceutique,
        'substances_actives': produit.substances_actives,
        'numero_autorisation_AMM': produit.numero_autorisation_AMM,
        'date_delivrance_AMM': produit.date_delivrance_AMM,
        'numero_decision_AMM': produit.numero_decision_AMM,
        'status_AMM': produit.status_AMM,
    }
    return JsonResponse(data)
@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def add_produit(request):
    if request.method == 'POST':
        form = ProduitForm(request.POST)
        if form.is_valid():
            produit = form.save()
            return JsonResponse({
                'id': produit.id,
                'nom_du_produit': produit.nom_du_produit,
                'classe_therapeutique': produit.classe_therapeutique,
                'familles_antibiotiques': produit.familles_antibiotiques,
                'forme_pharmaceutique': produit.forme_pharmaceutique,
                'substances_actives': produit.substances_actives,
                'numero_autorisation_AMM': produit.numero_autorisation_AMM,
                'date_delivrance_AMM': produit.date_delivrance_AMM,
                'numero_decision_AMM': produit.numero_decision_AMM,
                'status_AMM': produit.status_AMM,
            })
        else:
            return JsonResponse({'errors': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def add_partenaire(request):
    if request.method == 'POST':
        form = PartenaireForm(request.POST)
        if form.is_valid():
            partenaire = form.save()
            return JsonResponse({
                'id': partenaire.id,
                'nom': partenaire.nom,
            })
        else:
            return JsonResponse({'errors': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def add_firme(request):
    if request.method == 'POST':
        form = StructureForm(request.POST)
        if form.is_valid():
            firme = form.save()
            return JsonResponse({
                'id': firme.id,
                'structure': firme.structure,
            })
        else:
            return JsonResponse({'errors': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def add_structure_import(request):
    if request.method == 'POST':
        form = StructureForm(request.POST)
        if form.is_valid():
            structure_import = form.save()
            return JsonResponse({
                'id': structure_import.id,
                'structure': structure_import.structure,
            })
        else:
            return JsonResponse({'errors': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
@group_required('Administrateur Système','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def add_structure_export(request):
    if request.method == 'POST':
        form = StructureForm(request.POST)
        if form.is_valid():
            structure_export = form.save()
            return JsonResponse({
                'id': structure_export.id,
                'structure': structure_export.structure,
            })
        else:
            return JsonResponse({'errors': form.errors}, status=400)
    return JsonResponse({'error': 'Invalid request'}, status=400)



#######################################Fonctions dashborad################
@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def dashboard_produit(request):
    from django.db.models.functions import TruncMonth
    import pandas as pd
    annee = request.POST.get('annee')
    type_op = request.POST.get('type_op')
    structure_id = request.POST.get('structure')
    type_produit = request.POST.get('type_produit')

    structures = Structure.objects.all()
    enregistrements = Enregistrement.objects.all()

    if annee:
        enregistrements = enregistrements.filter(date_importation__year=annee)
    if type_op:
        enregistrements = enregistrements.filter(type_enregistrement=type_op)
    if structure_id:
        enregistrements = enregistrements.filter(structure_importatrice_id=structure_id)
    if type_produit:
        enregistrements = enregistrements.filter(produit__type_produit=type_produit)

    total_produits = Produit.objects.count()
    total_operations = enregistrements.count()
    produits_medicament = Produit.objects.filter(type_produit='MEDICAMENT')
    produits_avec_amm = produits_medicament.exclude(numero_autorisation_AMM__isnull=True).exclude(numero_autorisation_AMM__exact='')
    taux_amm = round(produits_avec_amm.count() / produits_medicament.count() * 100, 2) if produits_medicament.exists() else 0
    valeur_totale_operations = enregistrements.aggregate(total=Sum('valeur_financiere'))['total'] or 0

    # === 1. Graphique volume par type d'opération (simple)
    def generate_bar_chart(labels, values, title, show_ylabel=True):
        fig, ax = plt.subplots(figsize=(6, 4))
        bars = ax.bar(labels, values, color=['#007bff', '#dc3545', '#28a745', '#ffc107'])
        ax.set_title(title)
        if not show_ylabel:
            ax.set_yticks([])
        else:
            ax.set_ylabel("Quantité")
        for bar in bars:
            yval = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2, yval + 0.5, f'{yval:.0f}', ha='center', fontsize=9)
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        return base64.b64encode(buf.read()).decode('utf-8')

    chart_base64 = generate_bar_chart(
        ['Importation', 'Exportation', 'Fabrication', 'Dotation'],
        [
            enregistrements.aggregate(Sum('quantité_importée'))['quantité_importée__sum'] or 0,
            enregistrements.aggregate(Sum('quantité_exportée'))['quantité_exportée__sum'] or 0,
            enregistrements.aggregate(Sum('quantité_fabriquée'))['quantité_fabriquée__sum'] or 0,
            enregistrements.aggregate(Sum('quantité_de_la_dotation'))['quantité_de_la_dotation__sum'] or 0,
        ],
        "Volume total par type d’opération",
        show_ylabel=False
    )

    # === 2. Camembert : répartition par type de produit selon type_op
    chart_mensuel_base64 = ''
    field_map = {
        'IMPORTATION': 'quantité_importée',
        'EXPORTATION': 'quantité_exportée',
        'FABRICATION': 'quantité_fabriquée',
        'DOTATION': 'quantité_de_la_dotation'
    }
    field = field_map.get(type_op) if type_op else None

    if field:
        qs = enregistrements.values('produit__type_produit') \
            .annotate(qte=Sum(field)) \
            .order_by('produit__type_produit')

        df = pd.DataFrame(list(qs))

        if not df.empty and 'produit__type_produit' in df.columns and 'qte' in df.columns:
            df = df[df['qte'].notnull()]
            df['qte'] = pd.to_numeric(df['qte'], errors='coerce')
            df = df[df['qte'].notnull()]
            if not df.empty:
                fig, ax = plt.subplots(figsize=(6, 6))
                ax.pie(
                    df['qte'],
                    labels=df['produit__type_produit'],
                    autopct='%1.1f%%',
                    startangle=140
                )
                ax.set_title(f"Répartition par type de produit ({type_op.lower().capitalize()})")
                plt.tight_layout()
                buf = io.BytesIO()
                plt.savefig(buf, format='png')
                plt.close(fig)
                buf.seek(0)
                chart_mensuel_base64 = base64.b64encode(buf.read()).decode('utf-8')

    # === 3. Analyse par produit
    analyse_par_produit = []
    for prod in Produit.objects.all():
        enrs = enregistrements.filter(produit=prod)
        quant_sum = enrs.aggregate(
            q1=Sum('quantité_importée'), q2=Sum('quantité_exportée'),
            q3=Sum('quantité_fabriquée'), q4=Sum('quantité_de_la_dotation'))
        analyse_par_produit.append({
            'nom': prod.nom_du_produit,
            'type': prod.type_produit,
            'nb': enrs.count(),
            'quantite': sum([q or 0 for q in quant_sum.values()]),
            'valeur': enrs.aggregate(Sum('valeur_financiere'))['valeur_financiere__sum'] or 0,
            'amm': 'Oui' if prod.type_produit == 'MEDICAMENT' and prod.numero_autorisation_AMM else 'Non'
        })

    # === 4. Origine / Destination
    origine_destination = []
    for prod in Produit.objects.all():
        enrs = enregistrements.filter(produit=prod)
        origine_destination.append({
            'nom': prod.nom_du_produit,
            'fab': ", ".join([p for p in enrs.values_list('pays_de_fabrication__nom', flat=True).distinct() if p]),
            'imp': ", ".join([p for p in enrs.values_list('pays_importation__nom', flat=True).distinct() if p]),
            'exp': ", ".join([p for p in enrs.values_list('pays_exportation__nom', flat=True).distinct() if p]),
        })

    # === 5. Importations par structure
    importations_details = enregistrements.filter(type_enregistrement='IMPORTATION') \
        .values(
            'structure_importatrice__structure',
            'produit__nom_du_produit',
            'produit__type_produit',
            'pays_importation__nom'
        ).annotate(
            total_quantite=Sum('quantité_importée'),
            total_valeur=Sum('valeur_financiere')
        ).order_by('structure_importatrice__structure', 'produit__nom_du_produit')

    annees = Enregistrement.objects.dates('created_at', 'year')

    return render(request, 'produit/dashbord.html', {
        'total_produits': total_produits,
        'total_operations': total_operations,
        'taux_amm': taux_amm,
        'valeur_totale_operations': valeur_totale_operations,
        'chart_base64': chart_base64,
        'chart_mensuel_base64': chart_mensuel_base64,
        'analyse_par_produit': analyse_par_produit,
        'origine_destination': origine_destination,
        'importations_details': importations_details,
        'structure': structures,
        'annees': [a.year for a in annees],
    })


##########################excel##################################

@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires','Gestionnaire des Médicaments','Directeur de la Santé Animale')
def export_enregistrements_excel(request):
    # Récupérer les années disponibles
    annees_dotation = Enregistrement.objects.annotate(annee=ExtractYear('date_dotation')).values_list('annee', flat=True).distinct()
    annees_importation = Enregistrement.objects.annotate(annee=ExtractYear('date_importation')).values_list('annee', flat=True).distinct()
    annees_exportation = Enregistrement.objects.annotate(annee=ExtractYear('date_exportation')).values_list('annee', flat=True).distinct()
    annees_fabrication = Enregistrement.objects.annotate(annee=ExtractYear('date_de_fabrication')).values_list('annee', flat=True).distinct()
    
    # Filtrer les valeurs None
    annees_dotation = [annee for annee in annees_dotation if annee is not None]
    annees_importation = [annee for annee in annees_importation if annee is not None]
    annees_exportation = [annee for annee in annees_exportation if annee is not None]
    annees_fabrication = [annee for annee in annees_fabrication if annee is not None]

    # Fusionner toutes les années et les trier
    annees = sorted(set(annees_dotation) | set(annees_importation) | set(annees_exportation) | set(annees_fabrication))

    # Appliquer les filtres si une année et/ou un type d'opération est sélectionné
    selected_year = request.POST.get('annee')
    selected_operation = request.POST.get('operation')
    export = request.POST.get('export')
    filters = Q()

    if selected_year:
        filters |= Q(date_dotation__year=selected_year)
        filters |= Q(date_importation__year=selected_year)
        filters |= Q(date_exportation__year=selected_year)
        filters |= Q(date_de_fabrication__year=selected_year)
        
    if selected_operation:
        filters &= Q(type_enregistrement=selected_operation)
    enregistrements = Enregistrement.objects.select_related("produit").filter(filters)
   
    if not export:
        return render(request, 'produit/export_data.html', {'annees': annees, 'selected_year': selected_year, 'selected_operation': selected_operation,'enregistrements':enregistrements})
    
    # Créer un classeur et une feuille Excel
    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Enregistrements"

    # Ajouter les en-têtes de colonnes
    headers = [
        "ID", "Produit", "Classe Thérapeutique", "Familles Antibiotiques", "Forme Pharmaceutique",
        "Substances Actives", "Numéro AMM", "Numéro Décision AMM", "Date Délivrance AMM", "Status AMM",
        "Type", "Quantité", "Structure(importatrince/exportatrice/partenaire)","Fabricant",'Pays de fabrication', "Adresse", "Pays", "Date", "Valeur Financière", "Unité"
    ]
    sheet.append(headers)

    # Récupérer les données des enregistrements filtrés
    for enr in enregistrements:
        produit = enr.produit
        if enr.type_enregistrement == "DOTATION":
            quantite = enr.quantité_de_la_dotation
            firme_de_fabrication = enr.firme_de_fabrication
            structure = enr.partenaire_de_dotation
            adresse = enr.adresse_partenaire_dotation
            pays = "N/A"
            date = enr.date_dotation
        elif enr.type_enregistrement == "FABRICATION":
            quantite = enr.quantité_fabriquée
            firme_de_fabrication = enr.firme_de_fabrication
            adresse = "N/A"
            pays = "N/A"
            date = enr.date_de_fabrication
        elif enr.type_enregistrement == "IMPORTATION":
            quantite = enr.quantité_importée
            firme_de_fabrication = enr.firme_de_fabrication
            structure = enr.structure_importatrice
            adresse = enr.addresse_importateur
            pays = enr.pays_importation
            date = enr.date_importation
        elif enr.type_enregistrement == "EXPORTATION":
            quantite = enr.quantité_exportée
            firme_de_fabrication = enr.firme_de_fabrication
            structure = enr.structure_exportatrice
            adresse = enr.addresse_exportateur
            pays = enr.pays_exportation
            date = enr.date_exportation
        else:
            quantite = "N/A"
            structure = "N/A"
            firme_de_fabrication="N/A"
            adresse = "N/A"
            pays = "N/A"
            date = "N/A"

        sheet.append([
            enr.id,
            produit.nom_du_produit,
            produit.classe_therapeutique,
            produit.familles_antibiotiques,
            produit.forme_pharmaceutique,
            produit.substances_actives,
            produit.numero_autorisation_AMM,
            produit.numero_decision_AMM,
            produit.date_delivrance_AMM.strftime("%d-%m-%Y") if produit.date_delivrance_AMM else "N/A",
            produit.status_AMM,
            enr.type_enregistrement,
            quantite,
            structure.structure if enr.type_enregistrement!='DOTATION' else structure.nom,
            firme_de_fabrication.structure if firme_de_fabrication.structure else "N/A" ,
            enr.pays_de_fabrication.nom if enr.pays_de_fabrication else "N/A",
            adresse if adresse else "N/A",
            pays.nom if pays and hasattr(pays, 'nom') else "N/A",
            date.strftime("%d-%m-%Y") if date else "N/A",
            enr.valeur_financiere if enr.valeur_financiere else "N/A",
            enr.unité_de_la_quantité if enr.unité_de_la_quantité else "N/A",
        ])

    # Créer une réponse HTTP avec un fichier Excel
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="enregistrements.xlsx"'
    
    workbook.save(response)
    return response
