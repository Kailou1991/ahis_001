from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from functools import wraps

def group_required(*group_names):
    """
    Décorateur pour restreindre l'accès à une vue aux utilisateurs appartenant à des groupes spécifiques.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                # Si l'utilisateur n'est pas connecté, il est redirigé vers la page de connexion
                return redirect('login')  # Remplacez 'login' par l'URL name de votre page de connexion

            # Vérifie les groupes de l'utilisateur
            user_groups = set(request.user.groups.values_list('name', flat=True))
            required_groups = set(group_names)

            print(f"User groups: {user_groups}")
            print(f"Required groups: {required_groups}")

            if user_groups & required_groups:
                # Si l'utilisateur est dans l'un des groupes requis, on exécute la vue
                return view_func(request, *args, **kwargs)
            else:
                # Sinon, on redirige vers une vue d'accès refusé ou une autre page
                print(f"Accès refusé : utilisateur non membre des groupes requis.")
                return HttpResponseForbidden("Vous n'avez pas les permissions nécessaires pour accéder à cette page.")

        return _wrapped_view
    return decorator
