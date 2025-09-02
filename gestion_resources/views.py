
from django.shortcuts import render, get_object_or_404, redirect
from .models import Employe, HistoriqueCarriere,Direction
from .form import EmployeForm, HistoriqueCarriereForm,DocumentForm,FormationForm
from django.core.exceptions import ValidationError
from .models import Employe, HistoriqueCarriere,Formation
from gestion_documents.models import Document
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.shortcuts import render
from django.db.models import Count, Q
from .models import Poste, Employe, HistoriqueCarriere, Formation,Region
from datetime import datetime, date, timedelta
from django.shortcuts import render
from django.db.models import Count, Avg
from django.contrib.auth.decorators import login_required
from data_initialization.decorators import group_required
from datetime import datetime, date, timedelta
from django.shortcuts import render
from django.db.models import Count, Avg, F, ExpressionWrapper, IntegerField
from .models import Direction, Employe, Poste, Formation


@login_required
@group_required('Administrateur Système','RH admin')
def ajouter_modifier_employe(request, employe_id=None):
    employe = get_object_or_404(Employe, id=employe_id) if employe_id else None
    message = None

    if request.method == "POST":
        employe_form = EmployeForm(request.POST, instance=employe)
        historique_form = HistoriqueCarriereForm(request.POST)

        if employe_form.is_valid() and historique_form.is_valid():
            try:
                employe = employe_form.save(commit=False)
                date_debut_nouveau = historique_form.cleaned_data['date_debut']
                date_fin_nouveau = historique_form.cleaned_data.get('date_fin')
                type_changement = historique_form.cleaned_data['type_changement']
                remarque = historique_form.cleaned_data['remarque']
                poste_nouveau = employe_form.cleaned_data['poste']

                # Vérification des dates
                if date_debut_nouveau and date_fin_nouveau and date_debut_nouveau >= date_fin_nouveau:
                    raise ValidationError("La date de début doit être inférieure à la date de fin.")

                if employe.date_embauche and employe.date_embauche > date_debut_nouveau:
                    raise ValidationError("La date d'embauche doit être inférieure ou égale à la date de début.")

                # Sauvegarde de l'employé avant de travailler sur les objets liés
                employe.save()

                # Vérification de l'historique et des chevauchements
                dernier_historique = HistoriqueCarriere.objects.filter(employe=employe).order_by('-date_debut').first()

                if dernier_historique:
                    if not dernier_historique.date_fin:
                        if type_changement in ['Detachement', 'Disponibilité', 'Stage', 'Fin de contrat', 'Licenciement', 'Démission']:
                            dernier_historique.date_fin = date_fin_nouveau
                            dernier_historique.save()
                            dernier_historique.poste.statut = 'vacant'
                            dernier_historique.poste.save()
                        else:
                            raise ValidationError("L'employé doit terminer son poste actuel avant d'en occuper un nouveau.")

                   
                # Création d'un nouvel historique si le poste change
                if poste_nouveau and (not dernier_historique or dernier_historique.poste != poste_nouveau):
                    nouvel_historique = HistoriqueCarriere.objects.create(
                        employe=employe,
                        poste=poste_nouveau,
                        date_debut=date_debut_nouveau,
                        date_fin=date_fin_nouveau,
                        type_changement=type_changement,
                        remarque=remarque
                    )

                    # Mise à jour du statut du nouveau poste
                    if poste_nouveau and not date_fin_nouveau:
                        poste_nouveau.statut = 'occupé'
                        poste_nouveau.save()

                # Mise à jour de la position de l'employé
                if type_changement in ['Detachement', 'Disponibilité', 'Stage', 'Fin de contrat', 'Licenciement', 'Démission']:
                    employe.position = type_changement
                    employe.save()

                return redirect("liste_employes")

            except ValidationError as e:
                messages.error(request, str(e))

    else:
        employe_form = EmployeForm(instance=employe)
        dernier_historique = HistoriqueCarriere.objects.filter(employe=employe).order_by('-date_debut').first() if employe else None
        historique_form = HistoriqueCarriereForm(instance=dernier_historique)

    return render(request, 'GestionRessourceHumaine/form_employe.html', {
        'employe_form': employe_form,
        'historique_form': historique_form,
        'employe': employe,
        'message': message
    })



@login_required
@group_required('Administrateur Système','RH admin')
def detail_employe(request, employe_id):
    # Récupérer l'employé ou retourner une erreur 404 s'il n'existe pas
    employe = get_object_or_404(Employe, id=employe_id)
    
    # Récupérer les documents administratifs associés à l'employé
    documents = Document.objects.filter(employe=employe)
    carrieres = HistoriqueCarriere.objects.filter(employe=employe)
    formations = Formation.objects.filter(employe=employe)
    for carriere in carrieres:
        carriere.nombre_annees = calculer_nombre_annees(carriere.date_debut, carriere.date_fin)
    return render(request, 'GestionRessourceHumaine/detail_employe.html', {
        'employe': employe,
        'documents': documents,
        'carrieres': carrieres,
        'formations':formations
    })

@login_required
@group_required('Administrateur Système','RH admin')
def liste_employes(request):
    # Récupérer tous les employés avec leurs relations
    employes = Employe.objects.select_related(
        'poste__direction', 'poste__sous_direction', 'poste__region',
        'poste__departement', 'poste__commune', 'grade', 'echelon'
    ).all()

    # Passer les employés au template
    return render(request, 'GestionRessourceHumaine/liste_employe.html', {'employes': employes})


@login_required
@group_required('Administrateur Système','RH admin')
def mettre_a_jour_document(request, employe_id):
    employe = get_object_or_404(Employe, id=employe_id)
    message = None  # Variable pour stocker le message d'erreur

    if request.method == "POST":
        document_form = DocumentForm(request.POST, request.FILES)

        if document_form.is_valid():
            document = document_form.save(commit=False)
            document.employe = employe  # Associer automatiquement l'employé en cours
            document.save()
            return redirect("liste_employes")
        else:
            message = "Veuillez corriger les erreurs ci-dessous."

    else:
        document_form = DocumentForm()

    # Récupérer les documents administratifs associés à l'employé
    documents = Document.objects.filter(employe=employe)

    return render(request, 'GestionRessourceHumaine/update_document.html', {
        'document_form': document_form,
        'employe': employe,
        'documents': documents,
        'message': message  # Ajouter le message au contexte
    })


from datetime import datetime, date

def calculer_nombre_annees(date_debut, date_fin=None):
    if not date_fin:
        date_fin = datetime.today().date()  # Convertir en date
    if isinstance(date_debut, datetime):
        date_debut = date_debut.date()  # Convertir en date
    if date_debut:
        delta = date_fin - date_debut
        return round(delta.days / 365.25, 1)  # Diviser par 365.25 pour prendre en compte les années bissextiles
    return None

@login_required
@group_required('Administrateur Système','RH admin')
def historique_carriere(request, employe_id):
    employe = get_object_or_404(Employe, id=employe_id)
    carrieres = HistoriqueCarriere.objects.filter(employe=employe)

    for carriere in carrieres:
        carriere.nombre_annees = calculer_nombre_annees(carriere.date_debut, carriere.date_fin)

    return render(request, 'GestionRessourceHumaine/historique_carriere.html', {
        'employe': employe,
        'carrieres': carrieres
    })


@login_required
@group_required('Administrateur Système','RH admin')
def supprimer_historique(request, historique_id):
    historique = get_object_or_404(HistoriqueCarriere, id=historique_id)
    poste = historique.poste
    employe=historique.employe

    # Supprimer l'historique de carrière
    historique.delete()

    # Vérifier si le poste est occupé par un autre employé
    if not HistoriqueCarriere.objects.filter(poste=poste).exists():
        poste.statut = 'vacant'
        poste.save()

    
    carrieres = HistoriqueCarriere.objects.filter(employe=employe)

    for carriere in carrieres:
        carriere.nombre_annees = calculer_nombre_annees(carriere.date_debut, carriere.date_fin)

    messages.success(request, 'Historique de carrière supprimé et poste remis vacant.')
    return render(request, 'GestionRessourceHumaine/historique_carriere.html', {
        'employe': employe,
        'carrieres': carrieres
    })


@login_required
@group_required('Administrateur Système','RH admin')
def supprimer_document(request, document_id):
    document = get_object_or_404(Document, id=document_id)
    employe = document.employe
    
    # Supprimer le document
    document.delete()

    # Récupérer les documents restants de l'employé
    documents = Document.objects.filter(employe=employe)
    document_form = DocumentForm()
    return render(request, 'GestionRessourceHumaine/update_document.html', {
        'document_form': document_form,
        'employe': employe,
        'documents': documents,
    })




@login_required
@group_required('Administrateur Système','RH admin')
def formations_employe(request, employe_id):
    employe = get_object_or_404(Employe, id=employe_id)
    formations = Formation.objects.filter(employe=employe)

    if request.method == 'POST':
        form = FormationForm(request.POST)
        if form.is_valid():
            formation = form.save(commit=False)
            formation.employe = employe
            formation.save()
            messages.success(request, 'Formation ajoutée avec succès.')
            return redirect('formations_employe', employe_id=employe.id)
    else:
        form = FormationForm()

    return render(request, 'GestionRessourceHumaine/update_formation.html', {
        'employe': employe,
        'formations': formations,
        'formation_form': form
    })

@login_required
@group_required('Administrateur Système','RH admin')
def supprimer_formation(request, formation_id):
    formation = get_object_or_404(Formation, id=formation_id)
    employe = formation.employe
    

    # Supprimer la formation
    formation.delete()
    # Récupérer les formations restantes de l'employé
    formations = Formation.objects.filter(employe=employe)
    form = FormationForm()
    messages.success(request, 'Formation supprimée et poste remis vacant.')
    return render(request, 'GestionRessourceHumaine/update_formation.html', {
        'employe': employe,
        'formations': formations,
        'formation_form':form

    })


@login_required
@group_required('Administrateur Système','RH admin')
def tableau_de_bord(request):
    date_debut = request.POST.get('date_debut')
    date_fin = request.POST.get('date_fin')

    # Filtrer les postes vacants
    postes_vacants = Poste.objects.filter(statut='vacant').count()

    # Filtrer les employés en fonction de la position et de la période
    employes = Employe.objects.all()
    if date_debut and date_fin:
        employes = employes.filter(
            Q(historiquecarriere__date_debut__gte=date_debut) &
            Q(historiquecarriere__date_fin__lte=date_fin)
        )

    # Agréger les employés par position
    employes_par_position = employes.values('position').annotate(total=Count('id'))

    # Répartition des employés par grade
    employes_par_grade = employes.values('grade__nom').annotate(total=Count('id'))

    # Répartition des employés par échelon
    employes_par_echelon = employes.values('echelon__nom').annotate(total=Count('id'))

    # Compter les employés décédés et retraités
    employes_decedes = Employe.objects.filter(position='DECDE').count()
    employes_retraites = Employe.objects.filter(position='RETRAITE').count()

    # Historique des changements de poste
    historique_carriere = HistoriqueCarriere.objects.all()
    if date_debut and date_fin:
        historique_carriere = historique_carriere.filter(
            Q(date_debut__gte=date_debut) & Q(date_fin__lte=date_fin)
        )

    # Formations suivies par les employés
    formations = Formation.objects.all()
    if date_debut and date_fin:
        formations = formations.filter(
            Q(date_debut__gte=date_debut) & Q(date_fin__lte=date_fin)
        )

    context = {
        'postes_vacants': postes_vacants,
        'employes_par_position': employes_par_position,
        'employes_par_grade': employes_par_grade,
        'employes_par_echelon': employes_par_echelon,
        'employes_decedes': employes_decedes,
        'employes_retraites': employes_retraites,
        'historique_carriere': historique_carriere,
        'formations': formations,
        'date_debut': date_debut,
        'date_fin': date_fin,
    }

    return render(request, 'GestionRessourceHumaine/tableau_de_bord.html', context)



@login_required
@group_required('Administrateur Système','RH admin')
def tableau_de_bord_central(request):
    annees = range(datetime.now().year, 2010, -1)
    directions = Direction.objects.all()
    
    # Récupération des valeurs POST (avec gestion des erreurs)
    annee = request.POST.get('annee')
    direction_id = request.POST.get('direction')

    direction = Direction.objects.filter(id=direction_id).first() if direction_id else None
    # Filtrer les employés par année d'embauche et direction
    employes = Employe.objects.all()
    if direction:
        employes = employes.filter(poste__direction=direction)
    else:
        employes = employes.filter(poste__direction__isnull=False)
    if annee:
        employes = employes.filter(date_embauche__year=annee)

    # Gestion des postes vacants et occupés
    postes_vacants = Poste.objects.filter(statut='vacant')
    postes_occupes = Poste.objects.filter(statut='occupé')
    if direction:
        postes_vacants = postes_vacants.filter(statut='vacant',direction=direction)
        postes_occupes = postes_occupes.filter(statut='occupé',direction=direction)
    else:
        
        postes_vacants = postes_vacants.filter(statut='vacant',direction__isnull=False)
        postes_occupes = postes_occupes.filter(statut='occupé',direction__isnull=False)
  

    # Statistiques sur les employés
    employes_par_position = employes.values('position', 'poste__direction__nom', 'poste__sous_direction__nom').annotate(total=Count('id'))
    formations_recues = Formation.objects.filter(employe__in=employes).values(
        'intitule', 'institution', 'date_debut', 'date_fin', 'diplome_obtenu',
        'employe__nom', 'employe__prenom', 'employe__poste__direction__nom', 'employe__poste__sous_direction__nom'
    )

    # Calcul de l'âge moyen en années
    age_moyen = employes.annotate(
        age=ExpressionWrapper(
            date.today().year - F('date_naissance__year'),
            output_field=IntegerField()
        )
    ).aggregate(age_moyen=Avg('age'))

    # Filtrage des employés par statut
    employes_actifs = employes.filter(position='ACTIVE')
    employes_retraites = employes.filter(position='RETRAITE')
    employes_detaches = employes.filter(position='DETACHE')
    employes_retraite_5_ans = employes.filter(
        date_naissance__lte=date.today() - timedelta(days=365*60)
    )
    employes_disponibilite = employes.filter(position='DISPONIBILITE')

    # Création du contexte pour le template
    context = {
        'annees': annees,
        'directions': directions,
        'annee_post': annee,
        'direction_id': direction_id,
        'postes_vacants': postes_vacants.count(),
        'postes_vacants_list':postes_vacants,
        'postes_occupes': postes_occupes.count(),
        'employes_par_position': employes_par_position,
        'formations_recues': formations_recues,
        'age_moyen': age_moyen['age_moyen'],
        'employes_actifs': employes_actifs,
        'employes_retraites': employes_retraites,
        'employes_retraite_5_ans': employes_retraite_5_ans,
        'employes_detaches': employes_detaches,
        'employes_disponibilite': employes_disponibilite,
    }
    
    return render(request, 'GestionRessourceHumaine/tableau_bord_central.html', context)




@login_required
@group_required('Administrateur Système','RH admin')
def tableau_de_bord_regional(request):
    annees = range(datetime.now().year, 2010, -1)
    regions = Region.objects.all()
    # Récupération des valeurs POST (avec gestion des erreurs)
    annee = request.POST.get('annee')
    region_id = request.POST.get('region')

    region = Region.objects.filter(id=region_id).first() if region_id else None

    # Filtrer les employés par année d'embauche et direction
    employes = Employe.objects.all()
    if region:
        employes = employes.filter(poste__region=region)
    else:
        employes = employes.filter(poste__region__isnull=False)
    if annee:
        employes = employes.filter(date_embauche__year=annee,poste__region__isnull=False)
    

    if region:
        postes_vacants = Poste.objects.filter(statut='vacant', region=region)
        postes_occupes = Poste.objects.filter(statut='occupé', region=region)
    else:
    # Prendre tous les postes où la région existe mais n'est pas définie
        postes_vacants = Poste.objects.filter(statut='vacant', region__isnull=False)
        postes_occupes = Poste.objects.filter(statut='occupé', region__isnull=False)


    # Statistiques sur les employés
    employes_par_position = employes.values('position','poste__departement__Nom','poste__commune__Nom').annotate(total=Count('id'))
    formations_recues = Formation.objects.filter(employe__in=employes).values(
        'intitule', 'institution', 'date_debut', 'date_fin', 'diplome_obtenu',
        'employe__nom', 'employe__prenom', 'employe__poste__departement__Nom','employe__poste__commune__Nom'
    )

    # Calcul de l'âge moyen en années
    age_moyen = employes.annotate(
        age=ExpressionWrapper(
            date.today().year - F('date_naissance__year'),
            output_field=IntegerField()
        )
    ).aggregate(age_moyen=Avg('age'))

    # Filtrage des employés par statut
    employes_actifs = employes.filter(position='ACTIVE')
    employes_retraites = employes.filter(position='RETRAITE')
    employes_detaches = employes.filter(position='DETACHE')
    employes_retraite_5_ans = employes.filter(
        date_naissance__lte=date.today() - timedelta(days=365*60)
    )
    employes_disponibilite = employes.filter(position='DISPONIBILITE')

    # Création du contexte pour le template
    context = {
        'annees': annees,
        'regions': regions,
        'annee_post': annee,
        'region_id': region_id,
        'postes_vacants': postes_vacants.count(),
        'postes_vacants_list':postes_vacants,
        'postes_occupes': postes_occupes.count(),
        'employes_par_position': employes_par_position,
        'formations_recues': formations_recues,
        'age_moyen': age_moyen['age_moyen'],
        'employes_actifs': employes_actifs,
        'employes_retraites': employes_retraites,
        'employes_retraite_5_ans': employes_retraite_5_ans,
        'employes_detaches': employes_detaches,
        'employes_disponibilite': employes_disponibilite,
    }
    
    return render(request, 'GestionRessourceHumaine/tableau_bord_regional.html', context)