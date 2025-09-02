from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from django.db.models.signals import post_save, post_delete

from django.contrib.contenttypes.models import ContentType
from .models import LogEntry
from .middleware import get_current_user  # type: ignore # Importer la fonction pour récupérer l'utilisateur

###Signal pour la journalisation des operation CRUD

@receiver(post_save)
def log_create_update(sender, instance, created, **kwargs):
    if sender == LogEntry:
        return  # Éviter la boucle infinie

    user = get_current_user()  # Récupérer l'utilisateur actif
    action = 'Created' if created else 'Updated'
    model_name = sender.__name__
    object_id = instance.pk

    LogEntry.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        changes=str(instance.__dict__)
    )

@receiver(post_delete)
def log_delete(sender, instance, **kwargs):
    if sender == LogEntry:
        return  # Éviter la boucle infinie

    user = get_current_user()  # Récupérer l'utilisateur actif
    action = 'Deleted'
    model_name = sender.__name__
    object_id = instance.pk

    LogEntry.objects.create(
        user=user,
        action=action,
        model_name=model_name,
        object_id=object_id,
        changes=str(instance.__dict__)
    )

@receiver(user_logged_in)
def store_user_profile_in_session(sender, user, request, **kwargs):
    # Accéder au profil utilisateur
    user_profile = user.userprofile
    
    # Stocker les informations dans la session
    request.session['region_id'] = user_profile.region_id
    request.session['departement_id'] = user_profile.departement_id
    request.session['group_id'] = user_profile.group_id
    print(f"Session data set: {request.session.items()}")  

@receiver(user_logged_out)
def clear_user_session(sender, request, user, **kwargs):
    # Supprimer les informations spécifiques de la session
    request.session.pop('region_id', None)
    request.session.pop('departement_id', None)
    request.session.pop('group_id', None)
