from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum
from .models import Conge, TypeConge,Employe
from .forms import CongeForm
from django.http import JsonResponse
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from django.utils import timezone



def get_conge_duree_restante(employe, type_conge, conge_id=None):
    """
    Calcule l'historique de la durée restante de congé pour un employé et un type de congé donné.

    Args:
        employe: L'employé concerné.
        type_conge: Le type de congé en question.
        conge_id: (Optionnel) L'ID du congé actuel si on est en mode modification.

    Returns:
        dict: Un dictionnaire avec les années comme clés et les tuples 
              (jours restants, nombre de jours autorisés, durée totale déjà prise) comme valeurs.
    """
    type_conge_instance = TypeConge.objects.filter(id=type_conge).first()
    if not type_conge_instance:
        return {}  # Aucun type de congé trouvé

    nombre_jour_autorise = type_conge_instance.nombreJour or 0
    print(f"Type de congé: {type_conge_instance.nom}, Jours autorisés: {nombre_jour_autorise}")

    historique = {}

    # Récupérer toutes les années pour lesquelles l'employé a pris des congés
    annees = Conge.objects.filter(employe=employe, type_conge=type_conge).dates('date_debut', 'year')

    # Convertir en liste
    annees_list = [a.year for a in annees]
    print(f"Années trouvées: {annees_list}")

    if not annees_list:
        # Si aucune année trouvée, on met une entrée avec nombre_jour_autorise complet
        annee_actuelle = timezone.now().year
        historique[annee_actuelle] = (nombre_jour_autorise, nombre_jour_autorise, 0)
        print(f"⚠️ Aucun congé trouvé, allocation complète pour l'année {annee_actuelle}.")
        return historique  # On retourne immédiatement

    # Sinon, on calcule pour chaque année existante
    for annee in annees_list:
        duree_totale = Conge.objects.filter(
            employe=employe, 
            type_conge=type_conge,
            date_debut__year=annee
        ).exclude(id=conge_id).aggregate(total_duree=Sum('duree'))['total_duree'] or 0
        solde = Conge.objects.filter(
            employe=employe, 
            type_conge=type_conge,
            date_debut__year=annee
        ).exclude(id=conge_id).aggregate(total_solde=Sum('solde'))['total_solde'] or 0
       
        jours_restants = solde
        historique[annee] = (max(0, jours_restants), nombre_jour_autorise, duree_totale)

    return historique



def ajouter_modifier_conge(request, conge_id=None):
    conge = get_object_or_404(Conge, id=conge_id) if conge_id else None
    type_conges = TypeConge.objects.all()
    message = None  # Message d'erreur

    if request.method == "POST":
        form = CongeForm(request.POST, instance=conge)
        if form.is_valid():
            conge_instance = form.save(commit=False)

            # Vérification des dates
            if not conge_instance.date_debut or not conge_instance.date_fin:
                message = "Les dates de début et de fin sont obligatoires."
            elif conge_instance.date_debut < timezone.now().date() or conge_instance.date_fin < timezone.now().date():
                message = "Les dates doivent être supérieures ou égales à aujourd'hui."
            elif conge_instance.date_debut > conge_instance.date_fin:
                message = "La date de début ne peut pas être après la date de fin."

            if message:
                messages.error(request, message)
                return render(request, "absences/conge_form.html", {
                    "form": form,
                    "conge": conge,
                    "message": message,
                    "type_conge_data": {tc.id: {'nombreJour': tc.nombreJour} for tc in type_conges}
                })

            # Calcul de la durée du congé
            conge_instance.duree = (conge_instance.date_fin - conge_instance.date_debut).days + 1

            # Vérifier qu'il n'y a pas de chevauchement avec d'autres congés
            conges_existants = Conge.objects.filter(
                employe=conge_instance.employe,
                type_conge=conge_instance.type_conge,
                date_debut__year=conge_instance.date_debut.year
            ).exclude(id=conge_instance.id)

            if any(
                conge_instance.date_debut <= conge_existant.date_fin and 
                conge_instance.date_fin >= conge_existant.date_debut
                for conge_existant in conges_existants
            ):
                message = "La période de congé se superpose avec un congé déjà pris."
                messages.error(request, message)
                return render(request, "absences/conge_form.html", {
                    "form": form,
                    "conge": conge,
                    "message": message,
                    "type_conge_data": {tc.id: {'nombreJour': tc.nombreJour} for tc in type_conges}
                })

            try:
                # Récupérer les informations sur les jours restants
                nombre_jour_autorise = conge_instance.type_conge.nombreJour

                historique = get_conge_duree_restante(
                    employe=conge_instance.employe, 
                    type_conge=conge_instance.type_conge.id
                )
                
                annee_courante = conge_instance.date_debut.year
                
                solde, nombre_jour_autorise, duree_totale = historique.get(annee_courante, (nombre_jour_autorise, nombre_jour_autorise, 0))
                
                # Vérification du dépassement des jours autorisés
                reste=nombre_jour_autorise-duree_totale
                if (duree_totale + conge_instance.duree) > nombre_jour_autorise:
                    raise ValidationError(
                        f"La durée totale des congés pour {conge_instance.type_conge.nom} "
                        f"ne doit pas dépasser {nombre_jour_autorise} jours par an. "
                        f"(Pris cette année : {duree_totale} jours, Restants : {reste} jours)"
                    )

                # Mise à jour du solde
                conge_instance.solde = max(0, nombre_jour_autorise - (duree_totale + conge_instance.duree))

                # Enregistrement du congé
                conge_instance.save()
                messages.success(request, "Le congé a été enregistré avec succès.")
                return redirect("liste_conges")

            except ValidationError as e:
                message = str(e)
                messages.error(request, message)

    else:
        form = CongeForm(instance=conge)

    return render(request, "absences/conge_form.html", {
        "form": form,
        "conge": conge,
        "message": message,
        "type_conge_data": {tc.id: {'nombreJour': tc.nombreJour} for tc in type_conges}
    })

def liste_conges(request):
    conges = Conge.objects.all()
    conges_details = []

    for conge in conges:
        employe = get_object_or_404(Employe, id=conge.employe_id)
        type_conge = get_object_or_404(TypeConge, id=conge.type_conge_id)
        historique = get_conge_duree_restante(employe, type_conge.id)
        annee_courante = conge.date_debut.year
        duree_restante, nombre_jour_autorise, duree_totale = historique.get(annee_courante, (0, 0, 0))

        # Calculer la durée totale des congés pris pour l'année en cours
        duree_totale_annee = Conge.objects.filter(
            employe=employe,
            type_conge=type_conge,
            date_debut__year=annee_courante
        ).aggregate(total_duree=Sum('duree'))['total_duree'] or 0

        # Ajouter la durée du congé actuel
        duree_totale_annee += conge.duree

        # Calculer les jours restants
        duree_restante = nombre_jour_autorise - duree_totale_annee

        conge_detail = {
            "conge": conge,
            "employe": employe,
            "type_conge": type_conge,
            "duree_restante": max(0, duree_restante),
            "nombre_jour_autorise": nombre_jour_autorise,
            "duree_totale": duree_totale_annee
        }
        conges_details.append(conge_detail)

    return render(request, "absences/liste_conges.html", {"conges_details": conges_details})


def supprimer_conge(request, conge_id):
    conge = get_object_or_404(Conge, id=conge_id)
    if request.method == "POST":
        conge.delete()
        return redirect("liste_conges")
    return render(request, "absences/confirm_delete.html", {"conge": conge})



