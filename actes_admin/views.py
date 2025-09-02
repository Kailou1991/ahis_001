from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .forms import DemandeActeForm, DocumentFinalForm,AffectationForm
from .models import DemandeActe, SuiviDemande, Justificatif
from django.http import JsonResponse
from .models import TypeActe
from django.contrib import messages
from django.db.models import OuterRef, Subquery, Case, When, Value, IntegerField
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils.timezone import now
from .models import  EmailNotification
from data_initialization.decorators import group_required
from django.db.models import OuterRef, Subquery
from .models import AffectationSuivi
from collections import OrderedDict
from django.db.models import Count, F, Sum
from datetime import timedelta
from collections import defaultdict
from .models import DemandeActe,Region, PieceAFournir,SuiviDemande, TypeActe, CategorieActe, AffectationSuivi
import calendar



def envoyer_email_confirmation(nom_complet, email, acte_nom, date_operation, niveau, statut, demande, cc_list=None):
    from_email = f"Direction Générale des Services vétérinaires <{settings.DEFAULT_FROM_EMAIL}>"

    # Sujet et message pour l'usager
    subject_usager = f"Suivi de votre demande administrative : \"{acte_nom}\""

    message_usager = (
        f"Bonjour {nom_complet},\n\n"
        f"Nous vous informons que votre demande d’acte administratif intitulée :\n"
        f"\"{acte_nom}\" est actuellement en cours de traitement au niveau : {niveau.upper()}.\n"
        f"Statut actuel : {statut.upper()}\n"
        f"Date de l'opération : {date_operation.strftime('%d/%m/%Y à %Hh%M')}\n\n"
        f"📄 Résumé de votre demande :\n"
        f"- Nom : {demande.nom}\n"
        f"- Prénom : {demande.prenom}\n"
        f"- Grade : {demande.grade}\n"
        f"- Nationalité : {demande.nationalite}\n"
        f"- Contact : {demande.contact}\n"
        f"- Email : {demande.email}\n"
        f"- Région : {demande.region}\n"
        f"- Département : {demande.departement}\n"
        f"- Commune : {demande.commune}\n"
        f"- Catégorie : {demande.categorie}\n"
        f"- Acte : {demande.acte}\n"
        + (f"- Établissement : {demande.nom_etablissement}\n" if demande.nom_etablissement else "")
        + (f"- Produit importé/exporté : {demande.nom_produit_importe_ou_exporte}\n" if hasattr(demande, 'nom_produit_importe_ou_exporte') and demande.nom_produit_importe_ou_exporte else "")
        + (f"- Unité de transformation : {demande.nom_unité_transformation}\n" if hasattr(demande, 'nom_unité_transformation') and demande.nom_unité_transformation else "")
        + "\n\nVous recevrez une notification à chaque étape de traitement.\n\n"
        + "Cordialement,\nDirection Générale des Services vétérinaires"
    )

    # Sujet et message pour les responsables
    subject_cc = f"[Action requise] Nouvelle demande à traiter - Niveau : {niveau.upper()}"

    message_cc = (
        f"Bonjour,\n\n"
        f"Une nouvelle demande d’acte a été soumise par {nom_complet} et nécessite un traitement au niveau {niveau.upper()}.\n"
        f"Acte demandé : {acte_nom}\n"
        f"Date de soumission : {date_operation.strftime('%d/%m/%Y à %Hh%M')}\n"
        f"Statut actuel : {statut.upper()}\n\n"
        f"📄 Détails de la demande :\n"
        f"- Nom : {demande.nom}\n"
        f"- Prénom : {demande.prenom}\n"
        f"- Grade : {demande.grade}\n"
        f"- Nationalité : {demande.nationalite}\n"
        f"- Contact : {demande.contact}\n"
        f"- Email : {demande.email}\n"
        f"- Région : {demande.region}\n"
        f"- Département : {demande.departement}\n"
        f"- Commune : {demande.commune}\n"
        f"- Catégorie : {demande.categorie}\n"
        f"- Acte : {demande.acte}\n"
        + (f"- Établissement : {demande.nom_etablissement}\n" if demande.nom_etablissement else "")
        + (f"- Produit importé/exporté : {demande.nom_produit_importe_ou_exporte}\n" if hasattr(demande, 'nom_produit_importe_ou_exporte') and demande.nom_produit_importe_ou_exporte else "")
        + (f"- Unité de transformation : {demande.nom_unité_transformation}\n" if hasattr(demande, 'nom_unité_transformation') and demande.nom_unité_transformation else "")
        + "\n\nMerci de procéder au traitement dès que possible.\n\n"
        + "Direction Générale des Services vétérinaires"
    )

    # Email à l'usager
    email_usager = EmailMessage(subject_usager, message_usager, from_email, [email])
    for justificatif in demande.justificatifs.all():
        if justificatif.fichier:
            email_usager.attach_file(justificatif.fichier.path)
    email_usager.send(fail_silently=True)

    # Email aux responsables (copie)
    if cc_list:
        email_cc = EmailMessage(subject_cc, message_cc, from_email, cc_list)
        for justificatif in demande.justificatifs.all():
            if justificatif.fichier:
                email_cc.attach_file(justificatif.fichier.path)
        email_cc.send(fail_silently=True)



def soumettre_demande(request):
    if request.method == 'POST':
        form = DemandeActeForm(request.POST)
        files = request.FILES.getlist('justificatifs')

        if 'reload' in request.POST:
            return render(request, 'actes/soumettre_demande.html', {'form': form})

        if form.is_valid() and request.POST.get('valider') == 'soumettre':
            demande = form.save(commit=False)
            demande.save()

            for f in files:
                Justificatif.objects.create(demande=demande, nom=f.name, fichier=f)

            suivi = SuiviDemande.objects.create(
                demande=demande,
                niveau="departemental",
                statut="en_cours"
            )

            cc_depart = EmailNotification.objects.filter(
                niveau="departemental",
                departement=demande.departement,
                actif=True
            ).values_list('email', flat=True)

            envoyer_email_confirmation(
                nom_complet=f"{demande.nom} {demande.prenom}",
                email=demande.email,
                acte_nom=demande.acte.nom,
                date_operation=suivi.date_action,
                niveau=suivi.niveau,
                statut=suivi.statut,
                demande=demande,
                cc_list=list(cc_depart)
            )

            return render(request, 'actes/soumettre_demande.html', {
                'form': DemandeActeForm(),
                'confirmation': "✅ Votre demande a été soumise avec succès. Vous recevrez des notifications par e-mail à chaque étape du traitement."
            })
        else:
            return render(request, 'actes/soumettre_demande.html', {
                'form': form,
                'erreur': "❌ Erreur dans le formulaire. Veuillez corriger les champs en rouge."
            })
    else:
        form = DemandeActeForm()

    return render(request, 'actes/soumettre_demande.html', {'form': form})

#################Public sommission





def soumettre_demande_public(request):
    if request.method == 'POST':
        form = DemandeActeForm(request.POST)
        files = request.FILES.getlist('justificatifs')

        if 'reload' in request.POST:
            return render(request, 'actes/soumettre_demande.html', {'form': form})

        if form.is_valid() and request.POST.get('valider') == 'soumettre':
            demande = form.save(commit=False)
            demande.save()

            for f in files:
                Justificatif.objects.create(demande=demande, nom=f.name, fichier=f)

            suivi = SuiviDemande.objects.create(
                demande=demande,
                niveau="departemental",
                statut="en_cours"
            )

            cc_depart = EmailNotification.objects.filter(
                niveau="departemental",
                departement=demande.departement,
                actif=True
            ).values_list('email', flat=True)

            envoyer_email_confirmation(
                nom_complet=f"{demande.nom} {demande.prenom}",
                email=demande.email,
                acte_nom=demande.acte.nom,
                date_operation=suivi.date_action,
                niveau=suivi.niveau,
                statut=suivi.statut,
                demande=demande,
                cc_list=list(cc_depart)
            )

            return render(request, 'actes/public_soumission.html', {
                'form': DemandeActeForm(),
                'confirmation': "✅ Votre demande a été soumise avec succès. Vous recevrez des notifications par e-mail à chaque étape du traitement."
            })
        else:
            return render(request, 'actes/public_soumission.html', {
                'form': form,
                'erreur': "❌ Erreur dans le formulaire. Veuillez corriger les champs en rouge."
            })
    else:
        form = DemandeActeForm()

    return render(request, 'actes/public_soumission.html', {'form': form})


@login_required
def uploader_document_final(request, demande_id):
    demande = get_object_or_404(DemandeActe, id=demande_id)
    if not request.user.groups.filter(name="central").exists():
        return redirect('permission_refusee')
    dernier_suivi = demande.suivis.order_by('-date_action').first()
    if not (dernier_suivi and dernier_suivi.niveau == "ministere" and dernier_suivi.statut == "valide"):
        return redirect('detail_demande', demande_id=demande.id)
    if request.method == 'POST':
        form = DocumentFinalForm(request.POST, request.FILES, instance=demande)
        if form.is_valid():
            demande.statut = "delivre"
            form.save()
            return redirect('detail_demande', demande_id=demande.id)
    else:
        form = DocumentFinalForm(instance=demande)
    return render(request, 'actes/uploader_document_final.html', {'form': form, 'demande': demande})



from django.contrib.auth.models import User
@login_required
@group_required('Administrateur Système', 'Directeur Générale des services vétérinaires', 'Directeur de la Santé Animale', 'Agent de suivi de demande','Administrateur Régional','Administrateur Départemental')
def liste_demandes(request):
    statut_filtre = request.GET.get('statut')
    departement_id = request.session.get('departement_id')
    region_id = request.session.get('region_id')
    user_groups = request.user.groups.values_list('name', flat=True)

    demandes = DemandeActe.objects.all()

    # Filtrage pour les agents de suivi
    if "Agent de suivi de demande" in user_groups:
        user_id = request.user.id
        demande_ids = AffectationSuivi.objects.filter(agent_id=user_id).values_list('demande_id', flat=True)
        demandes = demandes.filter(id__in=demande_ids)

    if departement_id:
        demandes = demandes.filter(departement_id=departement_id)
    if region_id:
        demandes = demandes.filter(region_id=region_id)
    if statut_filtre:
        demandes = demandes.filter(statut=statut_filtre)

    # Annotation pour l’agent le plus récent
    last_affectation = AffectationSuivi.objects.filter(demande=OuterRef('pk')).order_by('-id')
    demandes = demandes.annotate(agent_id=Subquery(last_affectation.values('agent')[:1]))

    # Classement par priorité : statut en_cours en premier
    demandes = demandes.annotate(
        statut_order=Case(
            When(statut='en_cours', then=Value(0)),
            When(statut='valide', then=Value(1)),
            When(statut='rejete', then=Value(2)),
            When(statut='delivre', then=Value(3)),
            default=Value(4),
            output_field=IntegerField()
        )
    ).order_by('statut_order', '-date_soumission')

    agents = {u.id: u for u in User.objects.filter(id__in=[d.agent_id for d in demandes if d.agent_id])}

    niveaux_affectables = ["departemental", "regional", "ordre", "central"]

    context = {
        'demandes': demandes,
        'agents': agents,
        'statut_filtre': statut_filtre,
        'statuts': [
            ("en_cours", "En cours"),
            ("valide", "Validé"),
            ("rejete", "Rejeté"),
            ("delivre", "Délivré"),
        ],
        'niveaux_affectables': niveaux_affectables,
    }

    return render(request, 'actes/liste_demandes.html', context)


def load_actes(request):
    categorie_id = request.GET.get('categorie')

    if not categorie_id:
        return JsonResponse({'error': 'Categorie ID is required'}, status=400)

    try:
        actes = TypeActe.objects.filter(categorie_id=categorie_id).order_by('nom')
        data = [{'id': acte.id, 'nom': acte.nom} for acte in actes]
        return JsonResponse(data, safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    

   
def envoyer_email_affectation_agent(agent, demande, message_directeur):
    from_email = f"Direction Générale des Services vétérinaires <{settings.DEFAULT_FROM_EMAIL}>"
    subject = "Affectation d’une demande d’acte administratif – Action requise"

    message = (
        f"Madame, Monsieur {agent.get_full_name()},\n\n"
        f"Vous êtes désigné pour assurer le suivi et le traitement de la demande d’acte administratif ci-dessous :\n\n"
        f"📝 Informations sur la demande :\n"
        f"- Demandeur        : {demande.nom} {demande.prenom}\n"
        f"- Acte demandé     : {demande.acte}\n"
        f"- Catégorie        : {demande.categorie}\n"
        f"- Localisation     : {demande.commune}, {demande.departement}, {demande.region}\n"
        f"- Date de soumission : {demande.date_soumission.strftime('%d/%m/%Y à %Hh%M')}\n\n"
        f"📌 Instructions / commentaires du directeur :\n{message_directeur or 'Aucune instruction spécifique.'}\n\n"
        f"📎 Les pièces justificatives de la demande sont jointes à cet email.\n\n"
        f"Nous vous remercions de traiter cette demande dans les meilleurs délais.\n\n"
        f"Cordialement,\n"
        f"Direction Générale des Services Vétérinaires"
    )

    email = EmailMessage(subject, message, from_email, [agent.email])

    # 🔗 Ajouter les justificatifs en pièces jointes
    for justificatif in demande.justificatifs.all():
        if justificatif.fichier:
            email.attach_file(justificatif.fichier.path)

    email.send(fail_silently=True)



def envoyer_email_affectation_usager(demande, agent):
    from_email = f"Direction Générale des Services vétérinaires <{settings.DEFAULT_FROM_EMAIL}>"
    subject = "Affectation d’un agent pour le suivi de votre demande d’acte administratif"

    message = (
        f"Bonjour {demande.nom} {demande.prenom},\n\n"
        f"Votre demande d’acte administratif intitulée :\n"
        f"\"{demande.acte}\" ({demande.categorie})\n"
        f"est désormais prise en charge par un agent dédié pour son traitement.\n\n"
        f"📌 Coordonnées de l’agent en charge :\n"
        f"- Nom : {agent.get_full_name()}\n"
        f"- Email : {agent.email}\n"
        + (f"- Téléphone : {agent.profile.telephone}\n" if hasattr(agent, 'profile') and getattr(agent.profile, 'telephone', None) else "")
        + "\n\n"
        f"Nous vous invitons à contacter cet agent pour tout complément d'information ou suivi relatif à votre demande.\n\n"
        f"Cordialement,\n"
        f"Direction Générale des Services Vétérinaires"
    )

    EmailMessage(subject, message, from_email, [demande.email]).send(fail_silently=True)

@login_required
@group_required('Administrateur Système', 'Directeur Générale des services vétérinaires', 'Directeur de la Santé Animale')

def affecter_demande(request, pk):
    demande = get_object_or_404(DemandeActe, pk=pk)

    if request.method == 'POST':
        form = AffectationForm(request.POST, demande=demande)  # 👈 On passe la demande ici
        if form.is_valid():
            agent = form.cleaned_data['agent']

            deja_affecte = demande.affectations.filter(agent=agent).exists()
            if deja_affecte:
                messages.warning(request, f"⚠️ Cet agent ({agent.get_full_name()}) est déjà affecté à cette demande.")
            else:
                affectation = form.save(commit=False)
                affectation.demande = demande
                affectation.emetteur = request.user
                affectation.save()

                # Envoi des emails
                envoyer_email_affectation_agent(agent, demande, affectation.commentaire)
                envoyer_email_affectation_usager(demande, agent)

                messages.success(request, f"✅ La demande a été affectée avec succès à {agent.get_full_name()}.")
                return redirect('liste_demandes')
    else:
        form = AffectationForm(demande=demande)  # 👈 Passer aussi ici pour filtrer les agents

    return render(request, 'actes/affecter_demande.html', {
        'form': form,
        'demande': demande
    })


@login_required
@group_required('Administrateur Système', 'Directeur Générale des services vétérinaires', 'Directeur de la Santé Animale', 'Agent de suivi de demande','Administrateur Régional','Administrateur Départemental')
def details_acte(request, pk):
    demande = get_object_or_404(DemandeActe, id=pk)

    # Liste des niveaux dans l'ordre logique
    niveaux = ["departemental", "regional", "ordre", "central", "ministere"]

    # Dernier suivi par niveau (pour affichage synthétique)
    suivis_recents = OrderedDict()
    for niveau in niveaux:
        dernier_suivi = demande.suivis.filter(niveau=niveau).order_by('-date_action').first()
        if dernier_suivi:
            suivis_recents[niveau] = dernier_suivi

    # Tous les suivis pour l'historique complet
    historique = demande.suivis.order_by('date_action')

    justificatifs = demande.justificatifs.all()
    affectations = demande.affectations.select_related('agent')

    context = {
        'demande': demande,
        'suivis': suivis_recents.values(),  # Pour résumé par niveau
        'historique': historique,  # Pour afficher l'historique complet
        'justificatifs': justificatifs,
        'affectations': affectations,
        'niveaux': niveaux,
    }
    return render(request, 'actes/details_acte.html', context)


@login_required
@group_required('Administrateur Système','Directeur Générale des services vétérinaires',  'Directeur de la Santé Animale','Agent de suivi de demande')
def relancer_niveau(request, pk, niveau):
    demande = get_object_or_404(DemandeActe, id=pk)

    emails = EmailNotification.objects.filter(niveau=niveau, actif=True)
    if niveau == "departemental":
        emails = emails.filter(departement=demande.departement)
    elif niveau == "regional":
        emails = emails.filter(region=demande.region)

    destinataires = [notif.email for notif in emails]

    # Récupérer les agents de suivi de la demande
    agents_suivi = demande.affectations.select_related('agent')
    cc_list = [aff.agent.email for aff in agents_suivi if aff.agent.email]

    # Ajouter l'utilisateur connecté à la liste CC s'il a une adresse email
    if request.user.email:
        cc_list.append(request.user.email)

    if destinataires:
        subject = f"🔔 Relance de traitement - Demande d'acte administratif n°{demande.id}"
        message = (
            f"Madame, Monsieur,\n"
            f"Nous vous prions de bien vouloir examiner dans les meilleurs délais la demande suivante, en attente à votre niveau :\n\n"
            f"📝 Acte demandé : {demande.acte}\n"
            f"👤 Demandeur : {demande.nom} {demande.prenom}\n"
            f"📍 Localisation : {demande.commune}, {demande.departement}, {demande.region}\n"
            f"📅 Date de soumission : {demande.date_soumission.strftime('%d/%m/%Y à %Hh%M')}\n"
            f"🏛️ Niveau concerné : {niveau}\n"
            f"⏰ Date de relance : {now().strftime('%d/%m/%Y à %Hh%M')}\n\n"
            "Nous vous remercions de prendre les mesures nécessaires pour assurer le traitement rapide de cette demande.\n\n"
            "Cordialement,\n"
            "Direction Générale des Services vétérinaires"
        )

        email = EmailMessage(
            subject,
            message,
            f"Direction Générale des Services vétérinaires <{settings.DEFAULT_FROM_EMAIL}>",
            destinataires,
            cc=cc_list
        )
        email.send(fail_silently=True)
        messages.success(request, f"📤 Relance envoyée avec succès au niveau {niveau}.")
    else:
        messages.warning(request, f"⚠️ Aucun email configuré pour le niveau {niveau}.")

    return redirect('liste_demandes')





def get_niveau_suivant(demande, niveau_actuel):
    niveaux = ["departemental", "regional","central"]
    try:
        index = niveaux.index(niveau_actuel)
        return niveaux[index + 1] if index + 1 < len(niveaux) else None
    except ValueError:
        return None

def envoyer_notification_niveau(demande, niveau):
    subject = f"Notification - Votre demande passe au niveau {niveau.title()}"
    message = (
        f"Bonjour {demande.nom} {demande.prenom},\n\n"
        f"Votre demande d'acte \"{demande.acte}\" est maintenant au niveau \"{niveau.title()}\" pour traitement.\n\n"
        f"Cordialement,\nDirection Générale des Services vétérinaires"
    )
    from_email = f"Direction Générale des Services Vétérinaires <{settings.DEFAULT_FROM_EMAIL}>"
    EmailMessage(subject, message, from_email, [demande.email]).send(fail_silently=True)

    agents = demande.affectations.select_related('agent')
    for aff in agents:
        EmailMessage(
            f"Suivi - Transfert au niveau {niveau.title()}",
            f"Bonjour {aff.agent.get_full_name()},\n\nLa demande \"{demande.acte}\" a été transférée au niveau \"{niveau.title()}\".\n\nCordialement,\nDGSAV",
            from_email,
            [aff.agent.email]
        ).send(fail_silently=True)

    destinataires = EmailNotification.objects.filter(niveau=niveau, actif=True)
    if niveau == "departemental":
        destinataires = destinataires.filter(departement=demande.departement)
    elif niveau == "regional":
        destinataires = destinataires.filter(region=demande.region)

    for notif in destinataires:
        EmailMessage(
            f"Nouvelle demande à traiter - Niveau {niveau.title()}",
            f"Bonjour,\n\nUne nouvelle demande (\"{demande.acte}\") a été transférée pour traitement à votre niveau.\n\nMerci de procéder dans les meilleurs délais.\n\nCordialement,\nDGSAV",
            from_email,
            [notif.email]
        ).send(fail_silently=True)

@login_required
@group_required('Administrateur Système', 'Directeur Générale des services vétérinaires', 'Directeur de la Santé Animale', 'Agent de suivi de demande','Administrateur Régional','Administrateur Départemental')

def suivi_et_traitement_demande(request, pk):
    demande = get_object_or_404(DemandeActe, id=pk)
    suivi_actuel = demande.suivis.order_by('-date_action').first()

    if request.method == 'POST':
        traitement = request.POST.get('traitement', '').lower()
        motif_rejet = request.POST.get('motif_rejet', '')
        fichier = request.FILES.get('document_final')

        if traitement == 'valider_et_delivrer':
            if not fichier:
                messages.error(request, "❌ Veuillez joindre le document signé.")
                return redirect('suivi_traitement_demande', pk=demande.pk)

            # Enregistrement du fichier signé
            demande.document_final = fichier
            demande.statut = 'delivre'
            demande.save()

            # Enregistrer le statut validé puis délivré
            SuiviDemande.objects.create(demande=demande, niveau='central', statut='valide')
            SuiviDemande.objects.create(demande=demande, niveau='central', statut='delivre')

            envoyer_notification_niveau(demande, 'central')

            # Notification à l'usager
            subject = "📄 Votre acte administratif est prêt"
            message = (
                f"Bonjour {demande.nom} {demande.prenom},\n\n"
                f"Votre demande d'acte \"{demande.acte}\" a été traitée et validée. "
                f"L'acte signé est disponible en pièce jointe.\n\n"
                "Cordialement,\nDirection Générale des Services vétérinaires"
            )
            email = EmailMessage(subject, message, f"DGSAV <{settings.DEFAULT_FROM_EMAIL}>", [demande.email])
            email.attach(demande.document_final.name, fichier.read(), fichier.content_type)
            email.send(fail_silently=True)

            messages.success(request, "📄 L'acte a été validé et délivré.")

        elif traitement == 'valider':
            SuiviDemande.objects.create(demande=demande, niveau=suivi_actuel.niveau, statut='valide')
            prochain_niveau = get_niveau_suivant(demande, suivi_actuel.niveau)
            if prochain_niveau:
                SuiviDemande.objects.create(demande=demande, niveau=prochain_niveau, statut='en_cours')
                envoyer_notification_niveau(demande, prochain_niveau)
                messages.success(request, f"✅ La demande a été transférée au niveau {prochain_niveau}.")
            else:
                demande.statut = 'valide'
                demande.save()
                envoyer_notification_niveau(demande, suivi_actuel.niveau)
                messages.success(request, "✅ La demande a été validée définitivement.")

        elif traitement == 'rejeter':
            if not motif_rejet.strip():
                messages.error(request, "❌ Veuillez fournir un motif de rejet.")
            else:
                demande.statut = 'rejete'
                demande.save()
                SuiviDemande.objects.create(
                    demande=demande,
                    niveau=suivi_actuel.niveau,
                    statut='rejete',
                    motif_rejet=motif_rejet
                )
                envoyer_notification_niveau(demande, suivi_actuel.niveau)
                messages.warning(request, "❌ La demande a été rejetée.")

        return redirect('details_acte', pk=demande.pk)

    suivis = demande.suivis.order_by('date_action')
    return render(request, 'actes/suivi_traitement.html', {
        'demande': demande,
        'suivis': suivis,
        'suivi_actuel': suivi_actuel,
    })




@login_required
@group_required('Administrateur Système', 'Directeur Générale des services vétérinaires', 'Directeur de la Santé Animale', 'Agent de suivi de demande','Administrateur Régional','Administrateur Départemental')

def tableau_de_bord(request):
    today = now().date()
    first_day_of_month = today.replace(day=1)

    departement_id = request.session.get("departement_id")
    region_id = request.session.get("region_id") or request.GET.get("region")
    regions = Region.objects.all()

    demandes = DemandeActe.objects.all()
    if departement_id:
        demandes = demandes.filter(departement_id=departement_id)
    if region_id:
        demandes = demandes.filter(region_id=region_id)

    total_demandes = demandes.count()
    en_cours = demandes.filter(statut="en_cours").count()
    validees = demandes.filter(statut="valide").count()
    delivrees = demandes.filter(statut="delivre").count()
    rejetees = demandes.filter(statut="rejete").count()
    demandes_ce_mois = demandes.filter(date_soumission__gte=first_day_of_month).count()
    recettes = demandes.filter(statut="delivre").aggregate(total=Sum("acte__prix"))['total'] or 0

    # Moyennes de traitement
    delais_par_niveau = []
    niveaux = ["departemental", "regional", "ordre", "central"]
    for niveau in niveaux:
        suivis = SuiviDemande.objects.filter(niveau=niveau).order_by("demande", "date_action")
        delais, demandes_suivies = [], set()
        for suivi in suivis:
            if (suivi.demande.id, niveau) not in demandes_suivies:
                suivant = SuiviDemande.objects.filter(
                    demande=suivi.demande, date_action__gt=suivi.date_action
                ).order_by("date_action").first()
                if suivant:
                    delais.append((suivant.date_action - suivi.date_action).days)
                    demandes_suivies.add((suivi.demande.id, niveau))
        moyenne = round(sum(delais) / len(delais), 1) if delais else 0
        delais_par_niveau.append({"niveau": niveau.title(), "moyenne": moyenne})

    # Par catégorie
    repartition_categories = demandes.values(
        categorie_nom=F("categorie__nom")
    ).annotate(total=Count("id")).order_by("-total")

    # Évolution mensuelle
    mois_fr = {
        1: "Janvier", 2: "Février", 3: "Mars", 4: "Avril", 5: "Mai", 6: "Juin",
        7: "Juillet", 8: "Août", 9: "Septembre", 10: "Octobre", 11: "Novembre", 12: "Décembre"
    }
    evolution = defaultdict(int)
    for d in demandes:
        date = d.date_soumission
        evolution[f"{mois_fr[date.month]} {date.year}"] += 1
    evolution = sorted(evolution.items())

    # Recettes par type d’acte
    recettes_par_type = demandes.filter(statut="delivre").values(
        acte_nom=F("acte__nom")
    ).annotate(montant=Sum("acte__prix")).order_by("-montant")

    # Suivis en attente
    seuil = now() - timedelta(days=3)
    en_attente = SuiviDemande.objects.filter(statut="en_cours", date_action__lte=seuil)

    # Top agents
    top_agents = AffectationSuivi.objects.values(
        nom=F("agent__first_name"),
        prenom=F("agent__last_name")
    ).annotate(nb=Count("demande")).order_by("-nb")[:5]

    return render(request, "actes/dashboard.html", {
        "total_demandes": total_demandes,
        "en_cours": en_cours,
        "validees": validees,
        "delivrees": delivrees,
        "rejetees": rejetees,
        "recettes": recettes,
        "demandes_ce_mois": demandes_ce_mois,
        "repartition_categories": repartition_categories,
        "evolution": evolution,
        "delais_par_niveau": delais_par_niveau,
        "recettes_par_type": recettes_par_type,
        "en_attente": en_attente,
        "top_agents": top_agents,
        "regions": regions,
        "region_id": region_id,
    })




def centre_aide_documents(request):
    type_acte_id = request.GET.get("type_acte")

    types_actes = TypeActe.objects.all()
    pieces_qs = PieceAFournir.objects.select_related("type_acte", "type_acte__categorie")

    if type_acte_id:
        pieces_qs = pieces_qs.filter(type_acte_id=type_acte_id)

    # Group by type_acte
    pieces_grouped = {}
    for piece in pieces_qs:
        key = piece.type_acte
        if key not in pieces_grouped:
            pieces_grouped[key] = []
        pieces_grouped[key].append(piece)

    context = {
        "types_actes": types_actes,
        "pieces": pieces_grouped,
        "type_acte_id": type_acte_id,
    }
    return render(request, "actes/centre_aide_documents.html", context)
