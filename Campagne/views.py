from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from Campagne.models import Campagne
from datetime import datetime
from django.db import IntegrityError
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from .form import CampagneForm
from django.contrib import messages
from django.db import transaction, IntegrityError



@login_required
def liste_campagnes(request):
    # Récupérer toutes les campagnes et les trier par id
    campagnes = Campagne.objects.all().order_by('id')  

    # Vérifier si la dernière campagne est ouverte ou fermée
    last_campagne = campagnes.last() if campagnes.exists() else None

    # Si aucune campagne n'existe ou si la dernière est fermée, afficher le bouton pour en ouvrir une nouvelle
    show_new_campaign_button = not last_campagne or not last_campagne.statut

    return render(request, 'campagne/campagne_list.html', {
        'campagnes': campagnes,
        'show_new_campaign_button': show_new_campaign_button
    })

@login_required
def fermer_campagne(request, id):
    campagne = get_object_or_404(Campagne, id=id)

    # Fermer la campagne si elle est encore active
    if campagne.statut:
        campagne.statut = False
        campagne.save()
        message = f'✅ La campagne "{campagne}" a été fermée avec succès.'
    else:
        message = f'ℹ️ La campagne "{campagne}" était déjà fermée.'

    campagnes = Campagne.objects.all().order_by('-Campagne')

    return render(request, 'campagne/campagne_list.html', {
        'message': message,
        'campagnes': campagnes
    })


@login_required
def ajouter_campagne(request):
    message = ''
    if request.method == 'POST':
        form = CampagneForm(request.POST)
        if form.is_valid():
            campagne_nom = form.cleaned_data.get("Campagne")
            type_campagne = form.cleaned_data.get("type_campagne")

            # 1️⃣ Vérifier si une campagne identique existe déjà (nom + type)
            if Campagne.objects.filter(Campagne=campagne_nom, type_campagne=type_campagne).exists():
                message = "⚠️ Une campagne avec cette période et ce type existe déjà."
            else:
                with transaction.atomic():
                    # 2️⃣ Clôturer uniquement les campagnes actives de même type
                    Campagne.objects.filter(type_campagne=type_campagne, statut=True).update(statut=False)

                    # 3️⃣ Créer la nouvelle campagne comme active
                    campagne = form.save(commit=False)
                    campagne.user = request.user
                    campagne.statut = True
                    campagne.save()

                    return redirect('liste_campagnes')
    else:
        form = CampagneForm()

    return render(request, 'campagne/form.html', {
        'form': form,
        'message': message
    })

def supprimer_campagne(request, id):
    campagne = get_object_or_404(Campagne, id=id)

    if request.method == 'POST':
        campagne.delete()
        messages.success(request, f'✅ La campagne "{campagne}" a été supprimée avec succès.')
        return redirect('liste_campagnes')

    messages.error(request, '❌ Méthode non autorisée.')
    return redirect('liste_campagnes')


def get_type_campagne(request):
    campagne_id = request.GET.get('campagne_id')
    try:
        campagne = Campagne.objects.get(id=campagne_id)
        return JsonResponse({'type_campagne': campagne.get_type_campagne_display()})
    except Campagne.DoesNotExist:
        return JsonResponse({'type_campagne': ''})
