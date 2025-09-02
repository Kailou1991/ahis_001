import requests
from .models import SyncLog

def get_kobo_data(uid, token, base_url):
    url = f"{base_url}/api/v2/assets/{uid}/data.json"
    headers = {"Authorization": f"Token {token}"}
    response = requests.get(url, headers=headers, verify=False)
    response.raise_for_status()
    return response.json()["results"]

def sync_form(formulaire):
    from . import parsers

    data_list = get_kobo_data(formulaire.uid, formulaire.token, formulaire.base_url)
    parser_func = getattr(parsers, formulaire.parser)

    for submission in data_list:
        parser_func(submission, formulaire=formulaire)

    SyncLog.objects.create(
        formulaire=formulaire,
        status="SUCCES",
        message=f"{len(data_list)} enregistrements synchronisés."
    )
