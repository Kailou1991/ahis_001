# core/context_processors.py
import json, os
from django.conf import settings

def country_header(request):
    """
    Charge static/img/country_active.json et expose 'country' dans tous les templates.
    """
    path = os.path.join(settings.BASE_DIR, "static", "img", "country_active.json")
    data = {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        pass
    except Exception:
        pass

    # si vide, retourner un dict par défaut
    return {
        "country": data or {
            "pays": "",
            "drapeau": "",
            "armoirie": "",
            "appellation": "",
            "devise": "",
        }
    }
