import threading

_local = threading.local()

class CurrentUserMiddleware:
    """ Middleware pour stocker l'utilisateur actif dans le thread local """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _local.user = request.user if request.user.is_authenticated else None
        response = self.get_response(request)
        return response

def get_current_user():
    """ Récupère l'utilisateur courant stocké dans le thread local """
    return getattr(_local, 'user', None)
