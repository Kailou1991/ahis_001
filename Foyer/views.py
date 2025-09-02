from django.shortcuts import render, get_object_or_404, redirect
from reportlab.lib.pagesizes import landscape, A4
from django.db.models import Avg, F, ExpressionWrapper, fields
from datetime import timedelta
from reportlab.platypus import Spacer
import datetime
import matplotlib.cm as cm
import matplotlib.colors as mcolors
import requests
from datetime import datetime
import folium
from collections import defaultdict
from openpyxl import Workbook
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from django.db.models import Count, Sum,Q
from django.db.models.functions import TruncMonth
from .models import Region, Departement, Maladie, Commune  # Assurez-vous d'importer vos modèles
import random  # Pour générer des couleurs aléatoires
from django.http import HttpResponse
from .models import Foyer
from .form import FoyerForm
from django.db.models import Count
import matplotlib.pyplot as plt
import io
import base64
from .formPeriode import PeriodeRapportForm
from io import BytesIO
from django.http import JsonResponse
from .models import Foyer, Maladie, Region, Departement, Commune, Laboratoire, TypeTestLabo
from Espece.models import Espece
from django.db.models import Sum
import pandas as pd
from .formExcel import FoyerImportForm
from datetime import datetime
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib import messages
from rest_framework import viewsets
from .serializers import FoyerSerializer
from django.contrib.auth import authenticate, login as auth_login
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import user_passes_test
from data_initialization.decorators import group_required
from datetime import date
from reportlab.pdfgen import canvas
from .models import Foyer
import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
import os
from django.conf import settings  
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet
import plotly.express as px
import pandas as pd
import datetime
import io
import base64
import random
from collections import Counter
import matplotlib.pyplot as plt
from django.db.models import Count
from django.db.models.functions import TruncMonth
import math
from datetime import date


@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def foyer_list(request):
    user = request.user
    user_groups = set(user.groups.values_list('name', flat=True))

    # Champs ForeignKey à optimiser
    related_fields = [
        'region', 'departement', 'commune', 'maladie', 'espece',
        'laboratoire', 'type_test_labo', 'maladie_vaccination'
    ]

    if user_groups & {'Administrateur Système','Directeur Générale des services vétérinaires', 'Animateur de la Surveillance', 'Directeur de la Santé Animale'}:
        foyers = Foyer.objects.select_related(*related_fields)
    elif 'Administrateur Régional' in user_groups:
        region_id = request.session.get('region_id')
        if not region_id:
            return HttpResponseForbidden("La région de l'utilisateur n'est pas définie.")
        foyers = Foyer.objects.filter(region_id=region_id).select_related(*related_fields)
    elif 'Administrateur Départemental' in user_groups:
        departement_id = request.session.get('departement_id')
        if not departement_id:
            return HttpResponseForbidden("Le département de l'utilisateur n'est pas défini.")
        foyers = Foyer.objects.filter(departement_id=departement_id).select_related(*related_fields)
    else:
        return HttpResponseForbidden("Vous n'avez pas la permission d'accéder à cette page.")

    context = {'foyers': foyers}
    return render(request, 'Foyer/foyer_list.html', context)


##create
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def foyer_create(request):
   
    messages = None
    #data_list, fetch_messages = fetch_data_from_kobo()  # Récupérer les données et les messages
    
    #messages= fetch_messages if fetch_messages else []

    #if data_list:
       #insertion_messages = inserer_donnees_foyer(data_list)  # Récupérer les messages de la fonction
      # messages.extend(insertion_messages)
       #messages=None
    if request.method == 'POST':
        form = FoyerForm(request.POST, request.FILES)

        if form.is_valid():
            errors = []
            cd = form.cleaned_data
            today = date.today()

            # 1. Vérification des dates
            if cd['date_rapportage'] and cd['date_rapportage'] > today:
                errors.append("❌ La date de rapportage ne peut pas être postérieure à aujourd’hui.")
            if cd['date_rapportage'] and cd['date_envoi_prelevement'] and cd['date_rapportage'] > cd['date_envoi_prelevement']:
                errors.append("❌ La date de rapportage ne peut pas être après l'envoi des prélèvements.")
            if cd['date_envoi_prelevement'] and cd['date_reception_prelevement'] and cd['date_envoi_prelevement'] > cd['date_reception_prelevement']:
                errors.append("❌ L'envoi des prélèvements ne peut pas être après la réception.")
            if cd['date_reception_prelevement'] and cd['date_resultat'] and cd['date_reception_prelevement'] > cd['date_resultat']:
                errors.append("❌ La réception des prélèvements ne peut pas être après la date des résultats.")

            # 2. Vérification effectifs et échantillons (si pas d’erreurs précédentes)
            if not errors:
                effectif = cd.get('effectif_troupeau') or 0

                # Échantillons
                if not (
                    (cd.get('nbre_echant_positif') or 0) <= (cd.get('nbre_echant_recu') or 0) and
                    (cd.get('nbre_echant_inexploitable') or 0) <= (cd.get('nbre_echant_recu') or 0) and
                    ((cd.get('nbre_echant_positif') or 0) + (cd.get('nbre_echant_inexploitable') or 0)) <= (cd.get('nbre_echant_recu') or 0)
                ):
                    errors.append("❌ Les échantillons reçus doivent couvrir les positifs et les inexploités.")

                # Sujets animaux
                total_sujets = sum([
                    cd.get('nbre_sujets_malade') or 0,
                    cd.get('nbre_sujets_morts') or 0,
                    cd.get('nbre_sujets_vaccines') or 0,
                    cd.get('nbre_sujets_traites') or 0,
                    cd.get('nbre_sujets_abattus') or 0,
                    cd.get('nbre_sujets_en_quarantaine') or 0
                ])

                if total_sujets > effectif:
                    errors.append("❌ Le total des sujets (malades, morts, vaccinés, etc.) ne doit pas dépasser l’effectif du troupeau.")

            # 3. Traitement final
            if errors:
                for error in errors:
                    form.add_error(None, error)
            else:
                foyer = form.save(commit=False)
                foyer.user = request.user
                foyer.save()
                return redirect('foyer_list')
    else:
        form = FoyerForm()


    return render(request, 'Foyer/foyer_form.html', {'form': form, 'messages': messages})

##"update"
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def foyer_update(request, pk):
    foyer = get_object_or_404(Foyer, pk=pk)
    if request.method == 'POST':
        form = FoyerForm(request.POST, instance=foyer, user=request.user, session=request.session)
        
        if form.is_valid():
            # Récupération des champs de date
            date_rapportage = form.cleaned_data.get('date_rapportage')
            date_envoi_prelevement = form.cleaned_data.get('date_envoi_prelevement')
            date_reception_prelevement = form.cleaned_data.get('date_reception_prelevement')
            date_resultat = form.cleaned_data.get('date_resultat')
            date_du_jour = date.today()

            # Initialiser une liste d'erreurs
            errors = []

            # Vérification des dates
            if date_rapportage and date_rapportage > date_du_jour:
                errors.append("La date de rapportage ne peut pas être postérieure à aujourd'hui.")
            if date_rapportage and date_envoi_prelevement and date_rapportage > date_envoi_prelevement:
                errors.append("La date de rapportage ne peut pas être postérieure à la date d'envoi des prélèvements.")
            if date_envoi_prelevement and date_reception_prelevement and date_envoi_prelevement > date_reception_prelevement:
                errors.append("La date d'envoi des prélèvements ne peut pas être postérieure à la date de réception des prélèvements.")
            if date_reception_prelevement and date_resultat and date_reception_prelevement > date_resultat:
                errors.append("La date de réception des prélèvements ne peut pas être postérieure à la date des résultats.")

            # Vérifications des quantités
            if not errors:
                effectif = form.cleaned_data.get('effectif_troupeau') or 0
                nbre_sujets_malade = form.cleaned_data.get('nbre_sujets_malade') or 0
                nbre_sujets_morts = form.cleaned_data.get('nbre_sujets_morts') or 0
                nbre_sujets_vaccines = form.cleaned_data.get('nbre_sujets_vaccines') or 0
                nbre_sujets_abattus = form.cleaned_data.get('nbre_sujets_abattus') or 0
                nbre_sujets_traites = form.cleaned_data.get('nbre_sujets_traites') or 0
                nbre_sujets_quarantaines = form.cleaned_data.get('nbre_sujets_quarantaine') or 0
                nbre_echant_recu = form.cleaned_data.get('nbre_echant_recu') or 0
                nbre_echant_positif = form.cleaned_data.get('nbre_echant_positif') or 0
                nbre_echant_inexploitable = form.cleaned_data.get('nbre_echant_inexploitable') or 0

                # Vérification des contraintes sur les échantillons
                if not (
                    nbre_echant_positif <= nbre_echant_recu and
                    nbre_echant_inexploitable <= nbre_echant_recu and
                    nbre_echant_recu >= (nbre_echant_positif + nbre_echant_inexploitable)
                ):
                    errors.append("Erreur : le nombre total d'échantillons reçus doit être suffisant pour chaque catégorie d'échantillons. "
                                  "Le nombre d'échantillons positifs et inexploités doit être inférieur ou égal au nombre total d'échantillons reçus. "
                                  "De plus, la somme des échantillons positifs et inexploités ne doit pas dépasser le nombre d'échantillons reçus.")

                # Vérification des contraintes sur les sujets
                if not (
                    nbre_sujets_malade <= effectif and
                    nbre_sujets_morts <= effectif and
                    nbre_sujets_vaccines <= effectif and
                    nbre_sujets_traites <= effectif and
                    nbre_sujets_abattus <= effectif and
                    nbre_sujets_quarantaines <= effectif and
                    effectif >= (nbre_sujets_vaccines + nbre_sujets_traites + nbre_sujets_abattus + nbre_sujets_quarantaines) and
                    effectif >= (nbre_sujets_malade + nbre_sujets_morts)
                ):
                    errors.append("Erreur : l'effectif total du troupeau doit être suffisant pour chaque catégorie de sujets. "
                                  "Le nombre de sujets malades, morts, vaccinés, traités, abattus, et en quarantaine doit être inférieur ou égal à l'effectif total. "
                                  "De plus, la somme des sujets vaccinés, traités, abattus et en quarantaine ainsi que celle des sujets malades et morts "
                                  "ne doivent pas dépasser l'effectif total.")

            # Afficher les erreurs s'il y en a
            if errors:
                for error in errors:
                    form.add_error(None, error)
            else:
                # Si toutes les validations passent, on sauvegarde le formulaire
                sauvegarde = form.save(commit=False)
                sauvegarde.user = request.user
                sauvegarde.save()
                return redirect('foyer_list')
        
    else:
        form = FoyerForm(instance=foyer, user=request.user, session=request.session)

    if form.errors:
        form.add_error(None, "Veuillez corriger les erreurs ci-dessus.")

    return render(request, 'Foyer/foyer_form.html', {'form': form, 'foyer': foyer})

###delete
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def foyer_delete(request, pk):
    foyer = get_object_or_404(Foyer, pk=pk)
    if request.method == 'POST':
        foyer.delete()
        return redirect('foyer_list')
    return render(request, 'Foyer/foyer_confirm_delete.html', {'foyer': foyer})

# Filtrage dynamique
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def get_departements(request):
    region_id = request.session.get('region_id')
    departement_id = request.session.get('departement_id')
    if not region_id or (not region_id  and not departement_id ) :
        region_id = request.GET.get('region_id')
        departements = Departement.objects.filter(Region_id=region_id).values('id', 'Nom')
    elif region_id and not departement_id:
        departements = Departement.objects.filter(Region_id=region_id).values('id', 'Nom')
    elif region_id and departement_id:
        departements = Departement.objects.filter(Region_id=region_id,id=departement_id).values('id', 'Nom')
    return JsonResponse(list(departements), safe=False)
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def get_communes(request):
    departement_id = request.session.get('departement_id')
    if not departement_id:
      departement_id = request.GET.get('departement_id')
    communes = Commune.objects.filter(DepartementID_id=departement_id).values('id', 'Nom')
    return JsonResponse(list(communes), safe=False)

@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def get_maladie_type(request):
    maladie_id = request.GET.get('maladie_id')  # Récupérer le paramètre depuis la requête
    try:
        maladie = Maladie.objects.get(id=maladie_id)
        data = {'Maladie': maladie.Maladie}  # Assurez-vous que 'Type' est bien le champ correct
        return JsonResponse(data)
    except Maladie.DoesNotExist:
        return JsonResponse({'error': 'Maladie non trouvée'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)  # Gestion des autres exceptions


def get_maladies(request):
    espece_id = request.GET.get('espece_id')
    if espece_id:
        # Filtrer les maladies liées à l'espèce spécifique
        maladies = Maladie.objects.filter(Espece=espece_id).values('id', 'Maladie')
        print("maladies:",maladies)
        return JsonResponse(list(maladies), safe=False)
    else:
        # Retourner une réponse vide si aucun espece_id n'est fourni
        return JsonResponse([], safe=False)

####importation fichier excel
def convert_date(date_str):
    if isinstance(date_str, str):
        try:
            return datetime.strptime(date_str, '%d/%m/%Y').date()
        except ValueError:
            return None  # Retourne None si la date ne peut pas être convertie
    return None  # Retourne None si date_str n'est pas une chaîne de caractères



##import excel
@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def import_foyer_data(request):
    errors = []
    espece = None

    expected_columns = {
        'maladie', 'region', 'departement', 'commune', 'laboratoire', 'type_test_labo',
        'date_rapportage', 'localite', 'lieu_suspicion', 'nom_lieu_suspicion', 'longitude',
        'latitude', 'effectif_troupeau', 'nbre_sujets_malade', 'nbre_sujets_morts',
        'nbre_sujets_traites', 'nbre_sujets_vaccines', 'nbre_sujets_en_quarantaine',
        'nbre_sujets_abattus', 'nbre_humains_atteints', 'mesure_controle', 'prelevement_envoye',
        'date_envoi_prelevement', 'nature_prelevement', 'nbre_echantillon_prev', 'vaccinations_recentes',
        'maladie_vaccination', 'date_vaccination', 'resultat_laboratoire',
        'date_reception_prelevement', 'date_resultat', 'nbre_echant_recu', 'nbre_echant_positif',
        'nbre_echant_inexploitable', 'recommandations'
    }

    if request.method == 'POST':
        form = FoyerImportForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['file']
            df = pd.read_excel(excel_file)
            
            df = df.fillna('')

            actual_columns = set(df.columns)
            missing_columns = expected_columns - actual_columns
            extra_columns = actual_columns - expected_columns

            if missing_columns or extra_columns:
                errors.append("Le fichier Excel ne respecte pas la nomenclature des colonnes attendues.")
                if missing_columns:
                    errors.append(f"Colonnes manquantes : {', '.join(missing_columns)}")
                if extra_columns:
                    errors.append(f"Colonnes supplémentaires : {', '.join(extra_columns)}")
                return render(request, 'Foyer/import_foyer_data.html', {'form': form, 'errors': errors})

            for idx, row in df.iterrows():
                try:
                    with transaction.atomic():
                        maladie = None
                        region = None
                        departement = None
                        commune = None
                        laboratoire = None
                        type_test_labo = None
                        # Vérification ou création de l'espèce
                        if row.get('espece'):
                            espece, _ = Espece.objects.get_or_create(
                                Espece=row.get('espece')
                            )

                        # Vérification ou création de la maladie
                        if row.get('maladie'):
                            maladie, _ = Maladie.objects.get_or_create(
                                Maladie=row.get('maladie'),
                                Espece=espece  # Liez l'espèce à la maladie
                            )
                            
                        if row.get('region'):
                            region, _ = Region.objects.get_or_create(
                                Nom=row.get('region')
                            )
                            
                        if row.get('departement'):
                            departement, _ = Departement.objects.get_or_create(
                                Nom=row.get('departement'),
                                Region=region
                            )
                            
                        if row.get('commune'):
                            commune, _ = Commune.objects.get_or_create(
                                Nom=row.get('commune'),
                                DepartementID=departement
                            )
                            
                        if row.get('laboratoire'):
                            laboratoire, _ = Laboratoire.objects.get_or_create(
                                laboratoire=row.get('laboratoire')
                            )
                            
                        if row.get('type_test_labo'):
                            type_test_labo, _ = TypeTestLabo.objects.get_or_create(
                                test=row.get('type_test_labo')
                            )

                        def safe_int(val):
                            return int(val) if val != '' else 0

                        def safe_str(val):
                            return str(val) if val != '' else ''

                        def safe_date(val):
                            try:
                                return pd.to_datetime(val).date() if val != '' else None
                            except ValueError:
                                return None

                        # Vérifier si vaccinations_recentes est vide ou égal à "Non"
                        if row.get('vaccinations_recentes') in ['', 'Non']:
                            maladie_vaccination = ''
                            date_vaccination = None
                        else:
                            maladie_vaccination = maladie
                            date_vaccination = safe_date(row.get('date_vaccination'))

                        foyer_data = {
                            'date_rapportage': safe_date(row.get('date_rapportage')),
                            'maladie': maladie,
                            'region': region,
                            'departement': departement,
                            'commune': commune,
                            'localite': safe_str(row.get('localite')),
                            'lieu_suspicion': safe_str(row.get('lieu_suspicion')),
                            'nom_lieu_suspicion': safe_str(row.get('nom_lieu_suspicion')),
                            'longitude': safe_str(row.get('longitude')),
                            'latitude': safe_str(row.get('latitude')),
                            'effectif_troupeau': safe_int(row.get('effectif_troupeau')),
                            'nbre_sujets_malade': safe_int(row.get('nbre_sujets_malade')),
                            'nbre_sujets_morts': safe_int(row.get('nbre_sujets_morts')),
                            'nbre_sujets_traites': safe_int(row.get('nbre_sujets_traites')),
                            'nbre_sujets_vaccines': safe_int(row.get('nbre_sujets_vaccines')),
                            'nbre_sujets_en_quarantaine': safe_int(row.get('nbre_sujets_en_quarantaine')),
                            'nbre_sujets_abattus': safe_int(row.get('nbre_sujets_abattus')),
                            'nbre_humains_atteints': safe_int(row.get('nbre_humains_atteints')),
                            'mesure_controle': safe_str(row.get('mesure_controle')).split(','),
                            'prelevement_envoye': safe_str(row.get('prelevement_envoye')),
                            'date_envoi_prelevement': safe_date(row.get('date_envoi_prelevement')),
                            'nature_prelevement': safe_str(row.get('nature_prelevement')).split(','),
                            'nbre_echantillon_prev': safe_int(row.get('nbre_echantillon_prev')),
                            'vaccinations_recentes': safe_str(row.get('vaccinations_recentes')),
                            'maladie_vaccination': maladie_vaccination,
                            'date_vaccination': date_vaccination,
                            'resultat_laboratoire': safe_str(row.get('resultat_laboratoire')),
                            'date_reception_prelevement': safe_date(row.get('date_reception_prelevement')),
                            'date_resultat': safe_date(row.get('date_resultat')),
                            'nbre_echant_recu': safe_int(row.get('nbre_echant_recu')),
                            'nbre_echant_positif': safe_int(row.get('nbre_echant_positif')),
                            'nbre_echant_inexploitable': safe_int(row.get('nbre_echant_inexploitable')),
                            'laboratoire': laboratoire,
                            'type_test_labo': type_test_labo,
                            'recommandations': safe_str(row.get('recommandations')),
                        }

                        foyer_data = {k: v for k, v in foyer_data.items() if v is not None and v != ''}

                        Foyer.objects.create(**foyer_data)

                except (ValidationError, ValueError, TypeError) as e:
                    errors.append(f"Erreur lors de l'importation de la ligne {idx + 1}: {e}")
                    continue

            if not errors:
                messages.success(request, "Les données ont été importées avec succès.")

            return render(request, 'Foyer/import_foyer_data.html', {'form': form, 'errors': errors})
    
    else:
        form = FoyerImportForm()
    
    return render(request, 'Foyer/import_foyer_data.html', {'form': form, 'errors': errors})

@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def detail_foyer(request, pk):
    foyer = get_object_or_404(Foyer, pk=pk)  # Récupère l'enregistrement Foyer avec la clé primaire (pk)

    context = {
        'foyer': foyer,
    }
    return render(request, 'Foyer/foyer_detail.html', context) 





########################################################################
#                      Bulletin 
######################################################################""

@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires',
                'Administrateur Régional','Administrateur Départemental',
                'Animateur de la Surveillance','Directeur de la Santé Animale')

def generer_contenu_pdf_bulletin(request, buffer, foyers, start_date, end_date, periode_type, region_id, departement_id):
    """
    Bulletin PDF (A4 paysage) – version détaillée et professionnelle (sans cartes)
    Sections :
      - En‑tête (Ministère / Direction)
      - KPI / tuiles synthèse (foyers, sensibles, malades, morts, mortalité, morbidité, létalité)
      - Résumé exécutif
      - T1 : Indicateurs par maladie (+ graphique des taux)
      - T2 : Répartition par région (+ par département si non filtré au niveau département)
      - T3 : Laboratoire (si champs dispo)
      - T4 : Foyers récents (10 lignes)
      - Annexe : Liste complète (paginée automatiquement)
    """
    # === Imports locaux ===
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from django.db.models import Sum, Count
    from django.conf import settings
    from io import BytesIO
    import os
    import matplotlib.pyplot as plt

    # Modèles (adapte si besoin)
    from Foyer.models import Ministere, DirectionSV, Foyer
    from Region.models import Region
    from Departement.models import Departement

    # ---------- Helpers ----------
    def fmt_int(v):
        try:
            return f"{int(v):,}".replace(",", " ")
        except Exception:
            return "0"

    def pct(num, den):
        try:
            num = float(num or 0); den = float(den or 0)
            return round((num / den) * 100, 1) if den else 0.0
        except Exception:
            return 0.0

    def kpi_tile(label, value, sub=None, bg="#f8f9fa"):
        """Retourne un mini-tableau stylé façon carte KPI."""
        t = Table(
            [[Paragraph(f"<b>{label}</b>", styles["KPI_Label"])],
             [Paragraph(f"{value}", styles["KPI_Value"])],
             [Paragraph(sub or "", styles["KPI_Sub"])]],
            colWidths=[5.2*cm], rowHeights=[0.8*cm, 1.2*cm, 0.6*cm]
        )
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), colors.HexColor(bg)),
            ('BOX', (0,0), (-1,-1), 0.7, colors.HexColor("#dee2e6")),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        return t

    def zebra_style(tbl, header_bg="#0b5ed7"):
        tbl.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor(header_bg)),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 9),
            ('GRID', (0,0), (-1,-1), 0.35, colors.grey),
            ('ALIGN', (1,1), (-1,-1), 'CENTER'),
            ('FONTSIZE', (0,1), (-1,-1), 8),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.whitesmoke, colors.Color(0.98,0.98,0.98)]),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))

    # ---------- Styles ----------
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="TitreBleu", fontSize=16, leading=20, alignment=1, textColor=colors.darkblue))
    styles.add(ParagraphStyle(name="SousTitre", fontSize=11, leading=14, alignment=1, textColor=colors.black))
    styles.add(ParagraphStyle(name="NormalSmall", fontSize=8, leading=10))
    styles.add(ParagraphStyle(name="NormalCenter", fontSize=9, alignment=1))
    styles.add(ParagraphStyle(name="H2", fontSize=12, leading=15, spaceBefore=8, spaceAfter=6, textColor=colors.HexColor("#0b5ed7")))
    styles.add(ParagraphStyle(name="H3", fontSize=10, leading=13, spaceBefore=6, spaceAfter=4, textColor=colors.HexColor("#0b5ed7")))
    styles.add(ParagraphStyle(name="KPI_Label", fontSize=8, textColor=colors.HexColor("#6c757d")))
    styles.add(ParagraphStyle(name="KPI_Value", fontSize=16, leading=18, textColor=colors.HexColor("#212529")))
    styles.add(ParagraphStyle(name="KPI_Sub", fontSize=7, textColor=colors.HexColor("#6c757d")))

    # ---------- Document ----------
    doc = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=18, rightMargin=18, topMargin=18, bottomMargin=18
    )
    content = []

    # ---------- En-tête ----------
    ministere_nom = Ministere.objects.first().nom if Ministere.objects.exists() else "MINISTÈRE …"
    direction_nom = DirectionSV.objects.first().nom if DirectionSV.objects.exists() else "DIRECTION DES SERVICES VÉTÉRINAIRES"
    drapeau = os.path.join(settings.BASE_DIR, 'static/img/drapeau.jpg')
    armoirie = os.path.join(settings.BASE_DIR, 'static/img/armoirie.png')

    header = Table([[
        Image(drapeau, width=60, height=40) if os.path.exists(drapeau) else Paragraph("", styles["NormalSmall"]),
        Paragraph("<b>REPUBLIQUE DU SENEGAL<br/>UN PEUPLE – UN BUT – UNE FOI</b>", styles['NormalCenter']),
        Image(armoirie, width=60, height=60) if os.path.exists(armoirie) else Paragraph("", styles["NormalSmall"]),
    ]], colWidths=[70, 400, 70])
    content.extend([header, Spacer(1, 6)])

    content.append(Paragraph(ministere_nom.upper(), styles["TitreBleu"]))
    content.append(Paragraph(direction_nom.upper(), styles["SousTitre"]))
    content.append(Spacer(1, 4))

    # ---------- Titre et période ----------
    titre = f"Bulletin {periode_type} de situation zoosanitaire"
    if region_id:
        region_nom = Region.objects.filter(id=region_id).values_list('Nom', flat=True).first()
        if region_nom: titre += f" – Région : {region_nom}"
    if departement_id:
        departement_nom = Departement.objects.filter(id=departement_id).values_list('Nom', flat=True).first()
        if departement_nom: titre += f" – Département : {departement_nom}"
    content.append(Paragraph(titre, styles['H2']))
    content.append(Paragraph(f"Période : <b>{start_date.strftime('%d/%m/%Y')}</b> au <b>{end_date.strftime('%d/%m/%Y')}</b>", styles["Normal"]))

    # ---------- KPI Tiles ----------
    agg = foyers.aggregate(
        sens=Sum('effectif_troupeau'),
        mal=Sum('nbre_sujets_malade'),
        morts=Sum('nbre_sujets_morts'),
    )
    total_foyers = foyers.count()
    g_sens = agg.get('sens') or 0
    g_mal = agg.get('mal') or 0
    g_morts = agg.get('morts') or 0

    kpi_row1 = [
        kpi_tile("Foyers", fmt_int(total_foyers)),
        kpi_tile("Sensibles", fmt_int(g_sens)),
        kpi_tile("Malades", fmt_int(g_mal)),
        kpi_tile("Morts", fmt_int(g_morts)),
    ]
    kpi_row2 = [
        kpi_tile("Mortalité (%)", f"{pct(g_morts, g_sens):.1f}", "morts / sensibles", bg="#f1f3f5"),
        kpi_tile("Morbidité (%)", f"{pct(g_mal, g_sens):.1f}", "malades / sensibles", bg="#f1f3f5"),
        kpi_tile("Létalité (%)", f"{pct(g_morts, g_mal):.1f}", "morts / malades", bg="#f1f3f5"),
        kpi_tile("Période", f"{(end_date-start_date).days+1} j", f"{start_date:%d/%m} → {end_date:%d/%m/%Y}", bg="#f1f3f5"),
    ]
    content.extend([Table([kpi_row1], colWidths=[5.4*cm]*4, hAlign="LEFT", spaceBefore=6, spaceAfter=3),
                    Table([kpi_row2], colWidths=[5.4*cm]*4, hAlign="LEFT"),
                    Spacer(1, 8)])

    # ---------- Résumé exécutif ----------
    top_mal = list(
        foyers.values('maladie__Maladie')
              .annotate(m=Sum('nbre_sujets_malade'))
              .order_by('-m')[:3]
    )
    top_txt = ", ".join([f"{r['maladie__Maladie']} ({fmt_int(r['m'])})" for r in top_mal]) if top_mal else "—"
    resume = (
        f"<b>Résumé exécutif.</b> <b>{fmt_int(total_foyers)}</b> foyers enregistrés sur la période, "
        f"impliquant <b>{fmt_int(g_mal)}</b> sujets malades et <b>{fmt_int(g_morts)}</b> décès "
        f"(population sensible : {fmt_int(g_sens)}). "
        f"Pathologies dominantes (par cas) : {top_txt}."
    )
    content.extend([Paragraph(resume, styles["Normal"]), Spacer(1, 8)])

    # ---------- T1 : Par maladie + graphique des taux ----------
    content.append(Paragraph("Tableau 1 – Indicateurs par maladie", styles["H3"]))
    t1_header = ["Maladie", "Foyers", "Sensibles", "Malades", "Morts", "Mortalité %", "Morbidité %", "Létalité %"]
    t1_rows = [t1_header]

    stats_mal = (foyers.values('maladie__Maladie')
                        .annotate(
                            foy=Count('id'),
                            sens=Sum('effectif_troupeau'),
                            mal=Sum('nbre_sujets_malade'),
                            morts=Sum('nbre_sujets_morts'),
                        )
                        .order_by('-mal', 'maladie__Maladie'))

    labels, m_mor, m_morb, m_leta = [], [], [], []
    for r in stats_mal:
        mal_nom = r['maladie__Maladie'] or "—"
        sens, mal, morts = r['sens'] or 0, r['mal'] or 0, r['morts'] or 0
        mort_pct = pct(morts, sens)
        morb_pct = pct(mal, sens)
        leta_pct = pct(morts, mal)
        t1_rows.append([
            Paragraph(mal_nom, styles["NormalSmall"]),
            fmt_int(r['foy']), fmt_int(sens), fmt_int(mal), fmt_int(morts),
            f"{mort_pct:.1f}", f"{morb_pct:.1f}", f"{leta_pct:.1f}",
        ])
        labels.append(mal_nom); m_mor.append(mort_pct); m_morb.append(morb_pct); m_leta.append(leta_pct)

    t1 = Table(t1_rows, hAlign="LEFT")
    zebra_style(t1)
    content.append(t1)

    if labels:
        try:
            import numpy as np
            x = np.arange(len(labels)); width = 0.28
            fig, ax = plt.subplots(figsize=(8.8, 3.2))
            ax.bar(x - width, m_mor,  width, label='Mortalité %')
            ax.bar(x,         m_morb, width, label='Morbidité %')
            ax.bar(x + width, m_leta, width, label='Létalité %')
            ax.set_xticks(x); ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)
            ax.set_ylabel("Taux (%)"); ax.set_title("Taux par maladie")
            ax.legend(loc="upper left", ncol=3, fontsize=8)
            ax.grid(axis='y', linestyle='--', alpha=0.3)
            bio = BytesIO(); fig.tight_layout(); fig.savefig(bio, format='PNG', dpi=160); bio.seek(0)
            content.extend([Spacer(1, 6), Image(bio, width=560, height=240)])
            plt.close(fig)
        except Exception:
            pass

    content.append(Spacer(1, 8))

    # ---------- T2 : Répartition spatiale (Région / Département) ----------
    content.append(Paragraph("Tableau 2 – Répartition par région", styles["H3"]))
    t2_rows = [["Région", "Foyers", "Sensibles", "Malades", "Morts"]]
    stats_reg = (foyers.values('region__Nom')
                        .annotate(foy=Count('id'),
                                  sens=Sum('effectif_troupeau'),
                                  mal=Sum('nbre_sujets_malade'),
                                  morts=Sum('nbre_sujets_morts'))
                        .order_by('region__Nom'))
    for r in stats_reg:
        t2_rows.append([
            Paragraph(r['region__Nom'] or "—", styles["NormalSmall"]),
            fmt_int(r['foy']), fmt_int(r['sens'] or 0),
            fmt_int(r['mal'] or 0), fmt_int(r['morts'] or 0),
        ])
    t2 = Table(t2_rows, hAlign="LEFT", colWidths=[5.2*cm, 2.4*cm, 2.6*cm, 2.6*cm, 2.6*cm])
    zebra_style(t2)
    content.append(t2)

    # Si on n’est pas déjà filtré au niveau département : ajouter le détail départements
    if not departement_id:
        content.append(Spacer(1, 6))
        content.append(Paragraph("Détail – par département", styles["H3"]))
        t2b_rows = [["Département", "Foyers", "Sensibles", "Malades", "Morts"]]
        stats_dep = (foyers.values('departement__Nom')
                            .annotate(foy=Count('id'),
                                      sens=Sum('effectif_troupeau'),
                                      mal=Sum('nbre_sujets_malade'),
                                      morts=Sum('nbre_sujets_morts'))
                            .order_by('departement__Nom'))
        for r in stats_dep:
            t2b_rows.append([
                Paragraph(r['departement__Nom'] or "—", styles["NormalSmall"]),
                fmt_int(r['foy']), fmt_int(r['sens'] or 0),
                fmt_int(r['mal'] or 0), fmt_int(r['morts'] or 0),
            ])
        t2b = Table(t2b_rows, hAlign="LEFT", colWidths=[5.2*cm, 2.4*cm, 2.6*cm, 2.6*cm, 2.6*cm])
        zebra_style(t2b)
        content.append(t2b)

    content.append(Spacer(1, 8))

    # ---------- T3 : Laboratoire (si colonnes disponibles) ----------
    # Adapte les noms si besoin : resultat_laboratoire, nbre_echant_recu, nbre_echant_positif, type_test_labo, service_labo
    has_lab = True
    lab_cols = ["resultat_laboratoire", "nbre_echant_recu", "nbre_echant_positif"]
    for c in lab_cols:
        if not hasattr(Foyer, c):
            has_lab = False; break

    if has_lab:
        content.append(Paragraph("Tableau 3 – Activité de laboratoire", styles["H3"]))
        t3_rows = [["Maladie", "Éch. reçus", "Éch. positifs", "Taux positifs %"]]
        stats_lab = (foyers.values('maladie__Maladie')
                          .annotate(
                              recu=Sum('nbre_echant_recu'),
                              pos=Sum('nbre_echant_positif'),
                          )
                          .order_by('maladie__Maladie'))
        for r in stats_lab:
            recu = r['recu'] or 0; pos = r['pos'] or 0
            t3_rows.append([
                Paragraph(r['maladie__Maladie'] or "—", styles["NormalSmall"]),
                fmt_int(recu), fmt_int(pos), f"{pct(pos, recu):.1f}",
            ])
        t3 = Table(t3_rows, hAlign="LEFT", colWidths=[6.2*cm, 3.2*cm, 3.2*cm, 3.2*cm])
        zebra_style(t3)
        content.append(t3)
        content.append(Spacer(1, 8))

    # ---------- T4 : Foyers récents ----------
    content.append(Paragraph("Tableau 4 – Foyers récents (10 derniers)", styles["H3"]))
    recent = foyers.order_by('-date_rapportage')[:10]
    t4_rows = [["Date", "Localité (Commune)", "Maladie", "Sensibles", "Malades", "Morts", "Mesures"]]
    for f in recent:
        loc = f"{(f.localite or '').strip()} ({getattr(f.commune, 'Nom', '-')})"
        mesures = ", ".join(f.mesure_controle or []) if getattr(f, "mesure_controle", None) else "-"
        t4_rows.append([
            f.date_rapportage.strftime("%d/%m/%Y") if f.date_rapportage else "-",
            Paragraph(loc, styles["NormalSmall"]),
            Paragraph(getattr(f.maladie, 'Maladie', '-'), styles["NormalSmall"]),
            fmt_int(f.effectif_troupeau or 0),
            fmt_int(f.nbre_sujets_malade or 0),
            fmt_int(f.nbre_sujets_morts or 0),
            Paragraph(mesures, styles["NormalSmall"]),
        ])
    t4 = Table(t4_rows, hAlign="LEFT",
               colWidths=[2.2*cm, 5.4*cm, 3.6*cm, 2.2*cm, 2.2*cm, 2.2*cm, 7.0*cm])
    zebra_style(t4)
    content.append(t4)

    # ---------- Recommandations (brèves) ----------
    content.append(Spacer(1, 8))
    content.append(Paragraph("Recommandations prioritaires", styles["H3"]))
    reco = [
        "Maintenir la surveillance active dans les zones les plus touchées.",
        "Si mortalité/morbidité élevées : intensifier la sensibilisation et les mesures de biosécurité.",
        "Renforcer la notification précoce par les acteurs de terrain.",
        "Adapter les contrôles de mouvements d’animaux selon la dynamique observée.",
    ]
    content.append(Paragraph("• " + "<br/>• ".join(reco), styles["Normal"]))

    # ---------- Annexe : liste complète (paginée) ----------
    full_qs = (foyers
               .select_related("region", "departement", "commune", "maladie")
               .order_by('-date_rapportage', 'region__Nom', 'departement__Nom'))
    if full_qs.exists():
        content.append(PageBreak())
        content.append(Paragraph("Annexe – Liste détaillée des foyers", styles["H3"]))
        ann_headers = ["Date", "Région", "Département", "Commune", "Localité", "Maladie", "Sensibles", "Malades", "Morts"]
        rows = [ann_headers]
        count = 0
        for f in full_qs:
            rows.append([
                f.date_rapportage.strftime("%d/%m/%Y") if f.date_rapportage else "-",
                getattr(f.region, 'Nom', '-'),
                getattr(f.departement, 'Nom', '-'),
                getattr(f.commune, 'Nom', '-'),
                (f.localite or '').strip(),
                getattr(f.maladie, 'Maladie', '-'),
                fmt_int(f.effectif_troupeau or 0),
                fmt_int(f.nbre_sujets_malade or 0),
                fmt_int(f.nbre_sujets_morts or 0),
            ])
            count += 1
            # pagination douce : on coupe toutes les ~35 lignes
            if count % 35 == 0:
                t = Table(rows, hAlign="LEFT",
                          colWidths=[2.0*cm, 3.4*cm, 3.8*cm, 4.2*cm, 3.6*cm, 3.8*cm, 2.2*cm, 2.2*cm, 2.2*cm])
                zebra_style(t)
                content.append(KeepTogether([t, Spacer(1, 6)]))
                rows = [ann_headers]  # reset pour la page suivante
        # dernière page
        if len(rows) > 1:
            t = Table(rows, hAlign="LEFT",
                      colWidths=[2.0*cm, 3.4*cm, 3.8*cm, 4.2*cm, 3.6*cm, 3.8*cm, 2.2*cm, 2.2*cm, 2.2*cm])
            zebra_style(t)
            content.append(t)

    # ---------- Pied de page ----------
    content.append(Spacer(1, 10))
    content.append(Paragraph(
        f"<font size='8' color='#6c757d'>Bulletin généré automatiquement par AHIS – "
        f"{end_date.strftime('%d/%m/%Y')}.</font>", styles["Normal"]
    ))

    # Build
    doc.build(content)


def generer_bulletin(request):
    form = PeriodeRapportForm(request.POST or None)
    foyers = None
    start_date = None
    end_date = None
    error_message = None

    if request.method == 'POST' and form.is_valid():
        periode_type = form.cleaned_data['periode_type']
        annee = int(form.cleaned_data['annee'])
        today = date.today()
        region_id = request.session.get('region_id')
        departement_id = request.session.get('departement_id')

        def get_date_range():
            from datetime import datetime, date, timedelta
            if periode_type == 'Hebdomadaire' and form.cleaned_data.get('semaine'):
                semaine = int(form.cleaned_data['semaine'])
                start = datetime.strptime(f'{annee}-W{semaine}-1', "%Y-W%U-%w").date()
                
                end = min(start + timedelta(days=6), today)
                return start, end

            elif periode_type == 'Mensuel' and form.cleaned_data.get('mois'):
                mois = int(form.cleaned_data['mois'])
                start = date(annee, mois, 1)
                end = (start + timedelta(days=31)).replace(day=1) - timedelta(days=1)
                return start, min(end, today)

            elif periode_type == 'Trimestriel' and form.cleaned_data.get('trimestre'):
                trimestre = int(form.cleaned_data['trimestre'])
                start_end_map = {
                    1: (date(annee, 1, 1), date(annee, 3, 31)),
                    2: (date(annee, 4, 1), date(annee, 6, 30)),
                    3: (date(annee, 7, 1), date(annee, 9, 30)),
                    4: (date(annee, 10, 1), date(annee, 12, 31)),
                }
                start, end = start_end_map.get(trimestre, (None, None))
                return start, min(end, today)

            elif periode_type == 'Semestriel' and form.cleaned_data.get('semestre'):
                semestre = int(form.cleaned_data['semestre'])
                start = date(annee, 1, 1) if semestre == 1 else date(annee, 7, 1)
                end = date(annee, 6, 30) if semestre == 1 else date(annee, 12, 31)
                return start, min(end, today)

            elif periode_type == 'Annuel':
                return date(annee, 1, 1), min(date(annee, 12, 31), today)

            return None, None

        def get_filtered_foyers(start, end):
            queryset = Foyer.objects.filter(date_rapportage__range=(start, end))
            if region_id:
                queryset = queryset.filter(region=region_id)
            if departement_id:
                queryset = queryset.filter(departement=departement_id)
            return queryset

        # Calcul de la période et filtrage
        start_date, end_date = get_date_range()

        if start_date and end_date and start_date <= today:
            foyers = get_filtered_foyers(start_date, end_date)
        else:
            error_message = "Erreur : Veuillez sélectionner une période valide."

        # Génération du PDF si tout est OK
        if error_message is None:
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="bulletin_{periode_type}_{start_date.strftime("%Y%m%d")}_{end_date.strftime("%Y%m%d")}.pdf"'
            buffer = BytesIO()

            # Appel à la fonction qui construit le contenu du PDF
            generer_contenu_pdf_bulletin(request,
                buffer=buffer,
                foyers=foyers,
                start_date=start_date,
                end_date=end_date,
                periode_type=periode_type,
                region_id=region_id,
                departement_id=departement_id
            )

            pdf = buffer.getvalue()
            buffer.close()
            response.write(pdf)
            return response

    return render(request, 'Foyer/bulletin.html', {
        'form': form,
        'error_message': error_message
    })

@login_required
@group_required('Administrateur Système', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')


#dashbord

def get_filtre_session(region_id, departement_id):
    filtres = Q()
    if region_id:
        filtres &= Q(region_id=region_id)
    if departement_id:
        filtres &= Q(departement_id=departement_id)
    if region_id and departement_id:
        filtres &= Q(departement_id=departement_id,region=region_id)
    return filtres

@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def dashboardFoyer(request):
    region_session = request.session.get('region_id')
    departement_session = request.session.get('departement_id')
    filtres = get_filtre_session(region_session, departement_session) if region_session or departement_session else Q()

    foyers = Foyer.objects.filter(filtres).select_related(
        'region', 'departement', 'commune', 'maladie', 'espece',
        'laboratoire', 'type_test_labo', 'maladie_vaccination'
    )

    start_date = end_date = error_message = None
    maladieSelectione = regionSelectione = 0

    form = PeriodeRapportForm(request.POST or None, region_session=region_session)
    if request.method == 'POST' and form.is_valid():
        import datetime

        periode_type = form.cleaned_data['periode_type']
        annee = int(form.cleaned_data['annee'])
        maladieSelectione = form.cleaned_data.get('maladie') or 0
        regionSelectione = form.cleaned_data.get('region') or 0
        start_date, end_date = calculate_date_range(periode_type, annee, form, date.today())
        foyers = apply_filters(foyers, start_date, end_date, maladieSelectione, regionSelectione)

    # Graphiques serveur uniquement si foyers présents
    chart_data = generate_foyers_by_commune_chart(foyers) if foyers.exists() else None
    chart_data2 = generate_foyers_by_maladie_chart(foyers) if foyers.exists() else None
    chart_data3 = generate_monthly_trend_chart(foyers) if foyers.exists() else None
    chart_data4 = generate_histogram_by_month_chart(foyers) if foyers.exists() else None
    chart_data5 = generate_foyer_per_departement(foyers) if foyers.exists() else None
    char_region_radar = generate_foyers_by_region_radar_chart(foyers) if foyers.exists() else None
    char_region_donut_chart = generate_foyers_by_region_donut_chart(foyers) if foyers.exists() else None
    char_depart_stacked = generate_foyer_per_departement_stacked_area_chart(foyers) if foyers.exists() else None

    maladie_summary = generate_maladie_summary_table(foyers)
    maladie_summary_commune = generate_maladie_summary_commune(foyers)

    # Agrégats
    aggregates = foyers.aggregate(
        total_troupeau=Sum('effectif_troupeau'),
        total_malades=Sum('nbre_sujets_malade'),
        total_morts=Sum('nbre_sujets_morts'),
        total_traite=Sum('nbre_sujets_traites'),
    )

    total_foyers = foyers.count()
    nbre_kbt = foyers.filter(chiffre_kbt=True).count()
    nbre_foyer_prev = foyers.filter(prelevement_envoye__in=['OUI', 'oui']).count()
    nbre_foyer_resultat = foyers.filter(resultat_laboratoire__in=['OUI', 'oui']).count()
    total_troupeau = aggregates['total_troupeau'] or 0
    total_malades = aggregates['total_malades'] or 0
    total_morts = aggregates['total_morts'] or 0
    total_traite = aggregates['total_traite'] or 0

    TauxKBT = math.ceil((nbre_kbt / total_foyers) * 100) if total_foyers else 0
    TauxPrev = math.ceil((nbre_foyer_prev / total_foyers) * 100) if total_foyers else 0
    TauxResultat = math.ceil((nbre_foyer_resultat / total_foyers) * 100) if total_foyers else 0

    taux_letalite = (total_morts / total_malades) * 100 if total_malades else 0
    taux_morbidite = (total_malades / total_troupeau) * 100 if total_troupeau else 0
    taux_mortalite = (total_morts / total_troupeau) * 100 if total_troupeau else 0

    # Graphe taux (matplotlib)
    labels = ['Létalité', 'Morbidité', 'Mortalité']
    values = [taux_letalite, taux_morbidite, taux_mortalite]

    plt.figure(figsize=(6.5, 4))
    plt.bar(labels, values, color=['red', 'blue', 'green'])
    plt.xlabel('Taux')
    plt.ylabel('Pourcentage')
    plt.title('Situation épidémiologique de la maladie')
    plt.ylim(0, 100)
    for i, value in enumerate(values):
        plt.text(i, value + 1, f'{value:.2f}%', ha='center')

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    Graph_taux = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()

    # Délais moyens
    foyers_with_delivery_dates = foyers.filter(date_envoi_prelevement__isnull=False, date_reception_prelevement__isnull=False)
    avg_delivery = foyers_with_delivery_dates.annotate(
        delivery_delay=ExpressionWrapper(F('date_reception_prelevement') - F('date_envoi_prelevement'), output_field=DurationField())
    ).aggregate(avg=Avg('delivery_delay'))['avg'] or timedelta(0)

    foyers_with_result_dates = foyers.filter(date_reception_prelevement__isnull=False, date_resultat__isnull=False)
    avg_result = foyers_with_result_dates.annotate(
        result_delay=ExpressionWrapper(F('date_resultat') - F('date_reception_prelevement'), output_field=DurationField())
    ).aggregate(avg=Avg('result_delay'))['avg'] or timedelta(0)

    average_delivery_delay = f"{avg_delivery.days} jours et {avg_delivery.seconds // 3600} heures"
    average_result_delay = f"{avg_result.days} jours et {avg_result.seconds // 3600} heures"

    from Region.models import Region
    region = Region.objects.filter(id=region_session)
    map_html = generer_carte_foyers(foyers)
    resultats = calcul_indicateurs_foyers(foyers)

    context = {
        'form': form,
        'foyers': foyers,
        'map_html': map_html,
        'resultats': resultats,
        'Graph_taux': Graph_taux,
        'chart_data': chart_data,
        'chart_data2': chart_data2,
        'chart_data3': chart_data3,
        'chart_data4': chart_data4,
        'chart_data5': chart_data5,
        'char_region_radar': char_region_radar,
        'char_region_donut_chart': char_region_donut_chart,
        'char_depart_stacked': char_depart_stacked,
        'maladie_summary': maladie_summary,
        'maladie_summary_commune': maladie_summary_commune,
        'total_foyers': total_foyers,
        'total_malades': total_malades,
        'total_morts': total_morts,
        'total_traite': total_traite,
        'nbre_foyer_resultat': nbre_foyer_resultat,
        'average_delivery_delay': average_delivery_delay,
        'average_result_delay': average_result_delay,
        'TauxKBT': TauxKBT,
        'TauxPrev': TauxPrev,
        'TauxResultat': TauxResultat,
        'taux_letalite': taux_letalite,
        'taux_morbidite': taux_morbidite,
        'taux_mortalite': taux_mortalite,
        'maladieSelectione': maladieSelectione,
        'regionSelectione': regionSelectione,
        'error_message': error_message,
        'region_session': region_session,
        'region': region
    }

    return render(request, 'Foyer/dashbordFoyer.html', context)


def calculate_date_range(periode_type, annee, form, today):
   
    # Détermine les dates de début et de fin en fonction du type de période
    start_date, end_date = None, None
    
    from datetime import datetime, date, timedelta

    if periode_type == 'Hebdomadaire' and form.cleaned_data.get('semaine'):
        semaine_num = int(form.cleaned_data['semaine'])
        # Utilisation de la norme ISO 8601 (lundi = jour 1)
        start_date = datetime.strptime(f'{annee}-W{semaine_num}-1', "%G-W%V-%u").date()
        end_date = start_date + timedelta(days=6)
    elif periode_type == 'Mensuel' and form.cleaned_data.get('mois'):
        mois_num = int(form.cleaned_data['mois'])
        start_date = date(annee, mois_num, 1)
        end_date = (start_date + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    
    elif periode_type == 'Trimestriel' and form.cleaned_data.get('trimestre'):
        trimestre_num = int(form.cleaned_data['trimestre'])
        start_date, end_date = get_quarter_dates(annee, trimestre_num)
    
    elif periode_type == 'Semestriel' and form.cleaned_data.get('semestre'):
        semestre_num = int(form.cleaned_data['semestre'])
        start_date, end_date = get_semester_dates(annee, semestre_num)
    
    elif periode_type == 'Annuel':
        start_date = date(annee, 1, 1)
        end_date = date(annee, 12, 31)
    
    if end_date:
        end_date = min(end_date, today)
    
    return start_date, end_date


def apply_filters(qs, *, start_date, end_date, maladie_id=None, region_id=None, departement_id=None):
    """
    Applique les filtres dynamiquement sur le queryset des foyers.
    """
    filters = {}
    
    # Filtre par plage de dates
    if start_date and end_date:
        filters['date_rapportage__range'] = (start_date, end_date)
    
    # Filtre par maladie
    if maladie_id:
        filters['maladie_id'] = maladie_id
    
    # Filtre par région
    if region_id:
        filters['region_id'] = region_id
    
    # Filtre par département
    if departement_id:
        filters['departement_id'] = departement_id
    
    return qs.filter(**filters)


def generate_foyers_by_region_chart(foyers):
    # Génère un graphique du nombre de foyers par région
    foyers_by_region = foyers.values('region').annotate(count=Count('id'))
    region_names = [Region.objects.get(id=foyer['region']).Region for foyer in foyers_by_region]
    counts = [foyer['count'] for foyer in foyers_by_region]

    fig, ax = plt.subplots()
    ax.bar(region_names, counts, color='skyblue')
    ax.set_xlabel("Région")
    ax.set_ylabel("Nombre de foyers")
    ax.set_title("Nombre de foyers par région")
    plt.xticks(rotation=45)
    return convert_plot_to_base64(fig)


def generate_foyer_per_departement(foyers):
    """
    Génère un graphique du nombre de foyers par maladie et par département.
    """
    # Annoter le nombre de foyers par combinaison (Département, Maladie)
    foyers_by_departement = foyers.values('departement__Nom', 'maladie__Maladie').annotate(count=Count('id'))

    # Créer un DataFrame directement
    data = pd.DataFrame(list(foyers_by_departement))
    data.columns = ['Département', 'Maladie', 'Nombre de foyers']

    if data.empty:
        return None

    # Sécuriser le pivot avec agrégation si doublons
    pivot_data = data.pivot_table(index='Département', columns='Maladie', values='Nombre de foyers', aggfunc='sum', fill_value=0)

    # Création du graphique
    fig, ax = plt.subplots(figsize=(10, 6))

    bars = pivot_data.plot(kind='bar', ax=ax, colormap='tab20', width=0.6)

    ax.set_xlabel("Département")
    ax.set_ylabel("")
    ax.set_title("Nombre de foyers par maladie et par département")

    ax.yaxis.set_visible(False)
    plt.xticks(rotation=45, ha='right')
    ax.set_xticks(range(len(pivot_data.index)))
    ax.set_xticklabels(pivot_data.index, rotation=45, ha='right')

    ax.legend(title='Maladie', loc='upper right', bbox_to_anchor=(1.1, 1))

    # Afficher les étiquettes de données
    for container in bars.containers:
        bars.bar_label(container)

    return convert_plot_to_base64(fig)

def generate_maladie_summary_table(foyers):
    # Aggréger les données par maladie
    maladie_summary = foyers.values('maladie', 'region').annotate(
        nb_sujets_malades=Sum('nbre_sujets_malade'),
        nb_foyer =Count('maladie'),
        nb_sujets_morts=Sum('nbre_sujets_morts'),
        effectif_troupeau=Sum('effectif_troupeau'),
    )

    # Créer une liste de dictionnaires pour le tableau
    summary_data = []
    for entry in maladie_summary:
        maladie_name = Maladie.objects.get(id=entry['maladie']).Maladie
        region_name = Region.objects.get(id=entry['region']).Nom  # Assuming you have a Region model

        summary_data.append({
            'maladie': maladie_name,
            'region': region_name,
            'nb_foyer': entry['nb_foyer'],
            'nb_sujets_malades': entry['nb_sujets_malades'],
            'nb_sujets_morts': entry['nb_sujets_morts'],
            'effectif_troupeau': entry['effectif_troupeau']
        })
    summary_data.sort(key=lambda x: x['nb_foyer'], reverse=True)
    return summary_data

def generate_maladie_summary_commune(foyers):
    # Aggréger les données par maladie
    maladie_summary = foyers.values('maladie', 'commune').annotate(
        nb_sujets_malades=Sum('nbre_sujets_malade'),
        nb_foyer =Count('maladie'),
        nb_sujets_morts=Sum('nbre_sujets_morts'),
        effectif_troupeau=Sum('effectif_troupeau'),
    )

    # Créer une liste de dictionnaires pour le tableau
    summary_data = []
    for entry in maladie_summary:
        maladie_name = Maladie.objects.get(id=entry['maladie']).Maladie
        commune_name = Commune.objects.get(id=entry['commune']).Nom  # Assuming you have a Region model

        summary_data.append({
            'maladie': maladie_name,
            'commune': commune_name,
            'nb_foyer': entry['nb_foyer'],
            'nb_sujets_malades': entry['nb_sujets_malades'],
            'nb_sujets_morts': entry['nb_sujets_morts'],
            'effectif_troupeau': entry['effectif_troupeau']
        })
    summary_data.sort(key=lambda x: x['nb_foyer'], reverse=True)
    return summary_data


def generate_foyers_by_commune_chart(foyers):
    # Génère un graphique du nombre de foyers par commune
    foyers_by_commune = foyers.values('commune').annotate(count=Count('id'))
    commune_ids = [foyer['commune'] for foyer in foyers_by_commune]
    communes = Commune.objects.filter(id__in=commune_ids).values('Nom')
    commune_names = [commune['Nom'] for commune in communes]
    counts = [foyer['count'] for foyer in foyers_by_commune]
    colors = ['#%06X' % random.randint(0, 0xFFFFFF) for _ in range(len(commune_names))]
    fig, ax = plt.subplots()
    bars = ax.bar(commune_names, counts, color=colors)
    # Ajouter les étiquettes de données sur chaque barre
    for bar in bars:
        yval = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, yval, int(yval), va='bottom', ha='center') # va: vertical alignment, ha: horizontal alignment
    # Supprimer la graduation de l'axe Y
    ax.yaxis.set_ticks([])
    ax.set_xlabel('Commune')
    ax.set_ylabel('Nombre de foyers')
    ax.set_title('Nombre de foyers par commune')
    return convert_plot_to_base64(fig)


def generate_foyers_by_maladie_chart(foyers):
    # Génère un diagramme circulaire de répartition des foyers par maladie
    foyers_by_maladie = foyers.values('maladie').annotate(count=Count('id'))
    maladie_names = [Maladie.objects.get(id=foyer['maladie']).Maladie for foyer in foyers_by_maladie]
    counts_maladie = [foyer['count'] for foyer in foyers_by_maladie]
    
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.pie(counts_maladie, labels=maladie_names, startangle=100, shadow=True, radius=1.2, autopct='%1.1f%%')
    
    # Ajouter un titre avec un espacement supplémentaire
    ax.set_title("Répartition des foyers par maladie", pad=40)  # `pad` ajoute un espace entre le titre et le graphique
    
    # Ajuster la disposition pour éviter les chevauchements
    fig.tight_layout()
    
    return convert_plot_to_base64(fig)

def generate_monthly_trend_chart(foyers):
    # Génère un graphique de tendance mensuelle des foyers
    foyers_by_mois = foyers.annotate(month=TruncMonth('date_rapportage')).values('month').annotate(count=Count('id')).order_by('month')
    months = [foyer['month'].strftime("%b %Y") for foyer in foyers_by_mois]
    counts_month = [foyer['count'] for foyer in foyers_by_mois]

    # Créer un DataFrame pour faciliter le traçage
    data = pd.DataFrame({
        'Mois': months,
        'Nombre de foyers': counts_month
    })

    # Créer le Line Chart Boundaries
    fig, ax = plt.subplots()
    
    ax.plot(data['Mois'], data['Nombre de foyers'], marker='o', color="Slateblue", alpha=0.6, linewidth=2)
    ax.fill_between(data['Mois'], data['Nombre de foyers'], color="skyblue", alpha=0.4)

    ax.set_xlabel("Mois")
    ax.set_title("Tendance mensuelle des foyers")
    
    # Afficher les abscisses horizontalement
    plt.xticks(rotation=15)
    
    # Afficher le nombre de foyers sur le graphique avec un rectangle plus grand
    for i, txt in enumerate(data['Nombre de foyers']):
        ax.annotate(txt, (data['Mois'][i], data['Nombre de foyers'][i]), textcoords="offset points", xytext=(0,10), ha='center', bbox=dict(boxstyle="round,pad=0.3", edgecolor="black", facecolor="white"))
    
    # Supprimer l'axe Y
    ax.yaxis.set_visible(False)
    
    return convert_plot_to_base64(fig)



def generate_histogram_by_month_chart(foyers):
    # Génère un histogramme des foyers par mois
    months = [foyer.date_rapportage.month for foyer in foyers]
    month_counts = Counter(months)
    month_names = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin", "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
    colors = ['#%06X' % random.randint(0, 0xFFFFFF) for _ in range(len(month_names))]
    fig, ax = plt.subplots()
    ax.bar(month_names, [month_counts[i+1] for i in range(12)], color=colors, edgecolor="black")
    ax.set_xlabel("Mois de rapportage")
    ax.set_ylabel("Nombre de foyers")
    ax.set_title("Histogramme des foyers par mois de rapportage")
    plt.xticks(rotation=45)
    return convert_plot_to_base64(fig)

##########################################################
##########################################################
def generate_foyers_by_region_donut_chart(foyers):
    # Génère un graphique en anneau du nombre de foyers par région
    foyers_by_region = foyers.values('region').annotate(count=Count('id'))
    region_names = [Region.objects.get(id=foyer['region']).Nom for foyer in foyers_by_region]
    counts = [foyer['count'] for foyer in foyers_by_region]

    fig, ax = plt.subplots()
    ax.pie(counts, labels=region_names, autopct='%1.1f%%', startangle=140, pctdistance=0.85, colors=plt.cm.Paired.colors)
    centre_circle = plt.Circle((0,0),0.70,fc='white')
    fig.gca().add_artist(centre_circle)
    ax.set_title("Répartition des foyers par région")
    return convert_plot_to_base64(fig)

def generate_foyer_per_departement_stacked_area_chart(foyers):
    """
    Génère un graphique en aires empilées du nombre de foyers par maladie et par département.
    """
    # Compter les foyers par Département et Maladie
    foyers_by_departement = foyers.values('departement__Nom', 'maladie__Maladie').annotate(count=Count('id'))

    # Créer un DataFrame
    data = pd.DataFrame(list(foyers_by_departement))
    data.columns = ['Département', 'Maladie', 'Nombre de foyers']

    if data.empty:
        return None

    # Pivot sécurisé (gère les doublons)
    pivot_data = data.pivot_table(index='Département', columns='Maladie', values='Nombre de foyers', aggfunc='sum', fill_value=0)

    # Créer le graphique
    fig, ax = plt.subplots(figsize=(10, 6))
    pivot_data.plot(kind='area', stacked=True, ax=ax, colormap='tab20')

    ax.set_xlabel("Département")
    ax.set_ylabel("Nombre de foyers")
    ax.set_title("Nombre de foyers par maladie et par département")
    plt.xticks(rotation=45, ha='right')

    return convert_plot_to_base64(fig)

def generate_foyers_by_region_radar_chart(foyers):
    # Génère un graphique en radar du nombre de foyers par région
    foyers_by_region = foyers.values('region').annotate(count=Count('id'))
    region_names = [Region.objects.get(id=foyer['region']).Nom for foyer in foyers_by_region]  # Utiliser l'attribut correct pour le nom de la région
    counts = [foyer['count'] for foyer in foyers_by_region]

    # Préparer les données pour le graphique
    labels = region_names
    stats = counts

    # Créer le graphique
    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    stats += stats[:1]
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.fill(angles, stats, color='skyblue', alpha=0.25)
    ax.plot(angles, stats, color='Slateblue', linewidth=2)
    ax.set_yticklabels([])
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels)
    ax.set_title("Comparaison des foyers par région")
    
    # Ajouter une légende pour mieux comprendre le graphique
    legend_labels = [f"{label}: {count}" for label, count in zip(labels, counts)]
    ax.legend(legend_labels, loc='upper right', bbox_to_anchor=(1.1, 1.1))
    
    return convert_plot_to_base64(fig)


def generate_foyers_by_commune_scatter_plot(foyers):
    # Génère un graphique en nuage de points du nombre de foyers par commune et par maladie
    foyers_by_commune = foyers.values('commune', 'maladie').annotate(count=Count('id'))
    commune_names = [Commune.objects.get(id=foyer['commune']).Nom for foyer in foyers_by_commune]
    maladie_names = [Maladie.objects.get(id=foyer['maladie']).Maladie for foyer in foyers_by_commune]
    counts = [foyer['count'] for foyer in foyers_by_commune]

    fig, ax = plt.subplots()
    scatter = ax.scatter(commune_names, counts, c=maladie_names, cmap='viridis', alpha=0.6, edgecolors='w', linewidth=0.5)
    ax.set_xlabel("Commune")
    ax.set_ylabel("Nombre de foyers")
    ax.set_title("Nombre de foyers par commune et par maladie")
    plt.xticks(rotation=45, ha='right')
    legend1 = ax.legend(*scatter.legend_elements(), title="Maladie")
    ax.add_artist(legend1)
    
    return convert_plot_to_base64(fig)



def convert_plot_to_base64(fig):
    # Convertit un graphique matplotlib en base64 pour l'affichage dans le template
    buf = io.BytesIO()
    fig.savefig(buf, format='png')
    buf.seek(0)
    chart_data = base64.b64encode(buf.read()).decode('utf-8')
    buf.close()
    return chart_data


def get_quarter_dates(annee, trimestre_num):
    # Retourne les dates de début et de fin pour un trimestre donné
    if trimestre_num == 1:
        return date(annee, 1, 1), date(annee, 3, 31)
    elif trimestre_num == 2:
        return date(annee, 4, 1), date(annee, 6, 30)
    elif trimestre_num == 3:
        return date(annee, 7, 1), date(annee, 9, 30)
    elif trimestre_num == 4:
        return date(annee, 10, 1), date(annee, 12, 31)


def get_semester_dates(annee, semestre_num):
    # Retourne les dates de début et de fin pour un semestre donné
    if semestre_num == 1:
        return date(annee, 1, 1), date(annee, 6, 30)
    elif semestre_num == 2:
        return date(annee, 7, 1), date(annee, 12, 31)




##################################export et map data
@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires', 'Administrateur Régional','Administrateur Départemental','Animateur de la Surveillance','Directeur de la Santé Animale')
def export_foyer_excel(request):
    # 1) Portée session (région/département)
    region_session = request.session.get('region_id')
    departement_session = request.session.get('departement_id')
    filtres_session = get_filtre_session(region_session, departement_session) if (region_session or departement_session) else Q()

    # 2) Form en GET pour synchroniser carte + export
    form = PeriodeRapportForm(request.GET or None, region_session=region_session)

    # 3) Queryset initial borné par la session
    qs = (Foyer.objects
          .filter(filtres_session)
          .select_related("espece","maladie","region","departement","commune","laboratoire","type_test_labo"))

    # 4) Application des filtres du formulaire (si valides)
    filtered_qs = qs
    start_date = end_date = None

    if form.is_valid():
        periode_type = form.cleaned_data['periode_type']
        annee = int(form.cleaned_data['annee'])
        maladie_obj = form.cleaned_data.get('maladie')
        region_obj  = form.cleaned_data.get('region')

        today = date.today()
        start_date, end_date = calculate_date_range(periode_type, annee, form, today)

        filtered_qs = apply_filters(
            filtered_qs,
            start_date=start_date,
            end_date=end_date,
            maladie_id=(maladie_obj.id if maladie_obj else None),
            region_id=(region_obj.id if region_obj else None),
            departement_id=departement_session or None,
        )

    # 5) Si export demandé => renvoyer le fichier basé sur filtered_qs
    if request.GET.get('export') in ('1', 'xlsx', 'true'):
        return _build_foyers_xlsx(filtered_qs)

    # 6) Sinon on affiche la carte générée avec le même filtered_qs
    map_html = generer_carte_foyers(filtered_qs)
    ctx = {
        'form': form,
        'map_html': map_html,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'Foyer/export_foyer_maladies.html', ctx)


def _build_foyers_xlsx(queryset):
    """Construit le fichier Excel à partir du queryset filtré."""
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=foyers.xlsx'

    wb = Workbook()
    ws = wb.active
    ws.title = "Foyers"

    headers = [
        'ID', 'Date de Rapportage', 'Espèce', 'Maladie', 'Région', 'Département', 'Commune', 'Localité',
        'Lieu de Suspicion', 'Nom du Lieu', 'Longitude', 'Latitude', 'Effectif Troupeau',
        'Nb Sujets Malades', 'Nb Sujets Morts', 'Nb Cas Morsure Humains', 'Nb Cas Morsure Animaux',
        'Mesures de Contrôle', 'Nb Sujets Traités', 'Nb Sujets Vaccinés', 'Nb Sujets en Quarantaine',
        'Nb Sujets Abattus', 'Vaccinations Récentes', 'Maladie de Vaccination', 'Date de Vaccination',
        'Nature Prélèvement', 'Prélèvement Envoyé', 'Date Envoi Prélèvement', 'Date Réception Prélèvement',
        'Date Résultat', 'Résultat Labo', 'Laboratoire', 'Service Labo', 'Type de Test Labo',
        'Nb Échantillons Reçus', 'Nb Échantillons Positifs', 'Nb Échantillons Inexploitables',
        'Nb Échantillons Non conformes', 'Absence de Réactifs', 'Recommandations',
        'Fichier Résultat', 'Chiffre KBT', 'ID Kobo'
    ]
    ws.append(headers)

    for f in queryset.iterator():
        ws.append([
            f.id,
            getattr(f, 'date_rapportage', ''),
            str(getattr(f, 'espece', '') or ''),
            str(getattr(f, 'maladie', '') or ''),
            str(getattr(f, 'region', '') or ''),
            str(getattr(f, 'departement', '') or ''),
            str(getattr(f, 'commune', '') or ''),
            getattr(f, 'localite', '') or '',
            f.get_lieu_suspicion_display() if getattr(f, 'lieu_suspicion', None) else '',
            getattr(f, 'nom_lieu_suspicion', '') or '',
            getattr(f, 'longitude', '') or '',
            getattr(f, 'latitude', '') or '',
            getattr(f, 'effectif_troupeau', 0) or 0,
            getattr(f, 'nbre_sujets_malade', 0) or 0,
            getattr(f, 'nbre_sujets_morts', 0) or 0,
            getattr(f, 'nbre_des_cas_de_morsure_humains', 0) or 0,
            getattr(f, 'nbre_des_cas_de_morsure_animaux', 0) or 0,
            ', '.join(getattr(f, 'mesure_controle', []) or []),
            getattr(f, 'nbre_sujets_traites', 0) or 0,
            getattr(f, 'nbre_sujets_vaccines', 0) or 0,
            getattr(f, 'nbre_sujets_en_quarantaine', 0) or 0,
            getattr(f, 'nbre_sujets_abattus', 0) or 0,
            getattr(f, 'vaccinations_recentes', '') or '',
            str(getattr(f, 'maladie_vaccination', '') or ''),
            getattr(f, 'date_vaccination', '') or '',
            ', '.join(getattr(f, 'nature_prelevement', []) or []),
            getattr(f, 'prelevement_envoye', '') or '',
            getattr(f, 'date_envoi_prelevement', '') or '',
            getattr(f, 'date_reception_prelevement', '') or '',
            getattr(f, 'date_resultat', '') or '',
            getattr(f, 'resultat_laboratoire', '') or '',
            str(getattr(f, 'laboratoire', '') or ''),
            f.get_service_labo_display() if getattr(f, 'service_labo', None) else '',
            str(getattr(f, 'type_test_labo', '') or ''),
            getattr(f, 'nbre_echant_recu', 0) or 0,
            getattr(f, 'nbre_echant_positif', 0) or 0,
            getattr(f, 'nbre_echant_inexploitable', 0) or 0,
            getattr(f, 'nbre_echant_nonconforme', 0) or 0,
            'OUI' if getattr(f, 'absence_reactifs', False) else 'NON',
            getattr(f, 'recommandations', '') or '',
            (f.fichier_resultat.url if getattr(f, 'fichier_resultat', None) else ''),
            'OUI' if getattr(f, 'chiffre_kbt', False) else 'NON',
            getattr(f, 'idkobo', '') or '',
        ])

    wb.save(response)
    return response

############################################################################################
# Map pour les foyers
############################################################################################
def generer_carte_foyers(foyers_queryset):
    from collections import defaultdict
    import os, json
    import matplotlib.cm as cm
    import matplotlib.colors as mcolors
    from folium import Map, TileLayer, GeoJson, Circle, Element

    foyers_par_maladie = defaultdict(list)
    coords = []

    for foyer in foyers_queryset:
        if foyer.latitude and foyer.longitude:
            coords.append((foyer.latitude, foyer.longitude))
        if foyer.maladie:
            foyers_par_maladie[foyer.maladie.Maladie].append(foyer)

    # Centrage automatique
    if coords:
        moyenne_lat = sum(lat for lat, lon in coords) / len(coords)
        moyenne_lon = sum(lon for lat, lon in coords) / len(coords)
        m = Map(location=[moyenne_lat, moyenne_lon], zoom_start=6, control_scale=True)
    else:
        # Centrage Tchad (approx. N'Djamena)
        m = Map(location=[12.1348, 15.0557], zoom_start=6, control_scale=True)

    # Fond de carte clair
    TileLayer(
        tiles='https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png',
        attr='&copy; <a href="https://carto.com/">CartoDB</a>',
        name='CartoDB Positron',
        control=False
    ).add_to(m)

    # Contour GeoJSON du Tchad
    countries_path = os.path.join('static', 'geo', 'countries.geojson')
    if os.path.exists(countries_path):
        with open(countries_path, 'r', encoding='utf-8') as f:
            geo_data = json.load(f)

        tchad_feature = next(
            (feature for feature in geo_data['features']
             if feature['properties'].get('ADMIN') == 'Chad' or feature['properties'].get('name') == 'Chad'),
            None
        )

        if tchad_feature:
            GeoJson(
                tchad_feature,
                name='Tchad',
                style_function=lambda x: {
                    'fillColor': '#ffffff',
                    'color': '#000000',
                    'weight': 2,
                    'fillOpacity': 0.1
                }
            ).add_to(m)

    # Couleurs par maladie
    unique_maladies = list(foyers_par_maladie.keys())
    colormap = cm.get_cmap('tab20', len(unique_maladies))
    maladie_colors = {maladie: mcolors.to_hex(colormap(i)) for i, maladie in enumerate(unique_maladies)}

    # Légende
    legend_html = '''
    <style>
        #custom-legend {
            width: 100%;
            background-color: #ffffff;
            border-top: 1px solid #ccc;
            padding: 10px 20px;
            font-size: 13px;
            z-index: 9999;
            position: relative;
            margin: 0 auto;
            box-shadow: 0 -2px 6px rgba(0,0,0,0.1);
            max-height: 160px;
            overflow-y: auto;
        }
        #custom-legend .legend-title {
            font-weight: bold;
            text-align: center;
            margin-bottom: 10px;
        }
        #custom-legend .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 6px 20px;
        }
        #custom-legend .item {
            display: flex;
            align-items: center;
        }
        #custom-legend .item span.color {
            width: 14px;
            height: 14px;
            display: inline-block;
            margin-right: 6px;
            border-radius: 2px;
        }
    </style>
    <div id="custom-legend">
        <div class="legend-title">Légende des Maladies</div>
        <div class="grid">
    '''
    for maladie, color in maladie_colors.items():
        count = len(foyers_par_maladie[maladie])
        legend_html += f'''
            <div class="item">
                <span class="color" style="background:{color};"></span>
                <span>{maladie} ({count})</span>
            </div>
        '''
    legend_html += '''
        </div>
    </div>
    '''
    m.get_root().html.add_child(Element(legend_html))

    # Style global
    m.get_root().html.add_child(Element("""
    <style>
        body .content-scroll {
            overflow-y: hidden !important;
        }
        html, body {
            margin: 0;
            padding: 0;
            height: 100%;
            overflow-x: hidden !important;
            overflow-y: auto;
        }
        #map {
            height: calc(100vh - 180px) !important;
            width: 100vw !important;
            margin: 0 !important;
        }
        .folium-map {
            height: 100% !important;
        }
    </style>
    """))

    # Cercles des foyers
    for maladie, foyers_list in foyers_par_maladie.items():
        for foyer in foyers_list:
            if foyer.latitude and foyer.longitude:
                commune_nom = foyer.commune.Nom if hasattr(foyer.commune, 'Nom') else foyer.commune
                region_nom = foyer.region.Nom if hasattr(foyer.region, 'Nom') else foyer.region
                Circle(
                    location=[foyer.latitude, foyer.longitude],
                    radius=15000,
                    color=maladie_colors[maladie],
                    fill=True,
                    fill_color=maladie_colors[maladie],
                    popup=(f"<b>Maladie :</b> {maladie}<br>"
                           f"<b>Localisation :</b> {foyer.localite} ({commune_nom}, {region_nom})<br>"
                           f"<b>Effectif :</b> {foyer.effectif_troupeau}<br>"
                           f"<b>Malades :</b> {foyer.nbre_sujets_malade}<br>"
                           f"<b>Morts :</b> {foyer.nbre_sujets_morts}")
                ).add_to(m)

    return m._repr_html_()



################################################################################
################Calcul des indicateurs sur les delais###########################
################################################################################
from django.db.models import F, ExpressionWrapper, DurationField, FloatField, Case, When, Value
from django.db.models.functions import Cast
from django.db.models import Avg
def calcul_indicateurs_foyers(foyers_queryset):
    """
    Calcule les indicateurs de délais et de qualité des foyers à partir d'un queryset Foyer.
    Retourne un dictionnaire contenant les foyers annotés et les délais moyens en jours.
    """
    foyers_annotes = foyers_queryset.annotate(
        delai_prelevement_reception=ExpressionWrapper(
            F('date_reception_prelevement') - F('date_rapportage'),
            output_field=DurationField()
        ),
        delai_envoi_resultat=ExpressionWrapper(
            F('date_resultat') - F('date_envoi_prelevement'),
            output_field=DurationField()
        ),
        delai_total=ExpressionWrapper(
            F('date_resultat') - F('date_rapportage'),
            output_field=DurationField()
        ),
        taux_positif=ExpressionWrapper(
            Cast(F('nbre_echant_positif'), FloatField()) * 100.0 / Case(
                When(nbre_echant_recu__gt=0, then=F('nbre_echant_recu')),
                default=Value(1)
            ),
            output_field=FloatField()
        ),
        taux_nonconforme=ExpressionWrapper(
            Cast(F('nbre_echant_nonconforme'), FloatField()) * 100.0 / Case(
                When(nbre_echant_recu__gt=0, then=F('nbre_echant_recu')),
                default=Value(1)
            ),
            output_field=FloatField()
        ),
        taux_inexploitable=ExpressionWrapper(
            Cast(F('nbre_echant_inexploitable'), FloatField()) * 100.0 / Case(
                When(nbre_echant_recu__gt=0, then=F('nbre_echant_recu')),
                default=Value(1)
            ),
            output_field=FloatField()
        )
    )

    moyennes = foyers_annotes.aggregate(
        moy_delai_prelevement_reception=Avg('delai_prelevement_reception'),
        moy_delai_envoi_resultat=Avg('delai_envoi_resultat'),
        moy_delai_total=Avg('delai_total'),
    )

    def to_days(td):
        return round(td.total_seconds() / 86400, 2) if td else None

    return {
        'foyers': foyers_annotes,
        'moy_delai_prelevement_reception': to_days(moyennes['moy_delai_prelevement_reception']),
        'moy_delai_envoi_resultat': to_days(moyennes['moy_delai_envoi_resultat']),
        'moy_delai_total': to_days(moyennes['moy_delai_total']),
    }


class FoyerViewSet(viewsets.ModelViewSet):
    queryset = Foyer.objects.all()
    serializer_class = FoyerSerializer

