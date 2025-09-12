# kobo_bridge/utils.py
import requests
from urllib.parse import urljoin

# ---------------------------
# Découverte OData (si dispo)
# ---------------------------
def _odata_base_candidates(server_url: str, asset_uid: str):
    base = f"/api/v2/assets/{asset_uid}"
    # Plusieurs déploiements Kobo → on teste ces variantes
    return [
        urljoin(server_url, f"{base}/odata/"),
        urljoin(server_url, f"{base}/odata"),
        urljoin(server_url, f"{base}/odata/v1/"),
        urljoin(server_url, f"{base}/odata/v1"),
    ]

def odata_pick_entity(server_url: str, asset_uid: str, token: str) -> str:
    """
    Retourne l'URL COMPLÈTE de l'entité OData (ex: .../Submissions).
    1) Tente de lire le service document (JSON avec 'value': [{'url':'Submissions'}, ...])
    2) Sinon essaie 'Submissions'/'Items'/'data' en direct avec $top=1
    """
    headers = {"Authorization": f"Token {token}"}
    # 1) Service document
    for svc in _odata_base_candidates(server_url, asset_uid):
        try:
            r = requests.get(svc, headers=headers, timeout=30)
            if r.status_code == 200:
                js = r.json()
                sets = js.get("value") if isinstance(js, dict) else None
                if isinstance(sets, list) and sets:
                    for p in ("Submissions", "Items", "data"):
                        for es in sets:
                            if es.get("name") == p or es.get("url") == p:
                                return urljoin(svc if svc.endswith("/") else svc + "/", es.get("url"))
                    # sinon, premier set
                    return urljoin(svc if svc.endswith("/") else svc + "/", sets[0].get("url"))
        except Exception:
            pass
    # 2) Essais directs
    for svc in _odata_base_candidates(server_url, asset_uid):
        for ent in ("Submissions", "Items", "data"):
            try:
                test = urljoin(svc if svc.endswith("/") else svc + "/", ent)
                tr = requests.get(test, headers=headers, params={"$top": 1}, timeout=20)
                if tr.status_code == 200:
                    return test
            except Exception:
                pass
    raise RuntimeError("OData introuvable")

def odata_iter_rows(server_url: str, asset_uid: str, token: str, page_size=500):
    headers = {"Authorization": f"Token {token}"}
    url = odata_pick_entity(server_url, asset_uid, token)
    params = {"$top": page_size}
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=60)
        r.raise_for_status()
        data = r.json()
        for row in data.get("value", []):
            yield row
        next_link = data.get("@odata.nextLink") or data.get("@odata.nextlink") or data.get("@odata.next")
        if not next_link:
            break
        url = next_link
        params = {}

# ---------------------------
# Fallback REST JSON (si OData absente)
# ---------------------------
def _rest_base_candidates(server_url: str, asset_uid: str):
    base_api = f"/api/v2/assets/{asset_uid}"
    base_legacy = f"/assets/{asset_uid}"
    # Les 2 formats fréquents sur Kobo
    return [
        urljoin(server_url, f"{base_api}/submissions/?format=json"),
        urljoin(server_url, f"{base_api}/data/?format=json"),
        urljoin(server_url, f"{base_legacy}/submissions/?format=json"),  # <— ton lien
        urljoin(server_url, f"{base_legacy}/data/?format=json"),
    ]

def rest_iter_rows(server_url: str, asset_uid: str, token: str, page_size=500):
    """
    Itère les soumissions via l'API REST JSON.
    Gère pagination via 'next' si présente ; sinon lit la liste telle quelle.
    """
    headers = {"Authorization": f"Token {token}"}
    last_err = None
    for start_url in _rest_base_candidates(server_url, asset_uid):
        try:
            # si l'endpoint supporte page_size
            url = start_url
            seen = 0
            while url:
                params = {}
                # certains endpoints acceptent 'page_size'
                if "submissions" in url and "page_size=" not in url:
                    params["page_size"] = page_size
                r = requests.get(url, headers=headers, params=params, timeout=60)
                if r.status_code == 404:
                    break  # essaye l'URL suivante
                r.raise_for_status()
                js = r.json()
                # Format 1: {count, next, previous, results:[...] }
                if isinstance(js, dict) and "results" in js:
                    rows = js.get("results", [])
                    for row in rows:
                        yield row
                        seen += 1
                    url = js.get("next")
                    continue
                # Format 2: liste brute
                if isinstance(js, list):
                    for row in js:
                        yield row
                        seen += 1
                    url = None
                    continue
                # Format 3: {data:[...]} ou autre clé
                for key in ("data", "submissions", "items", "value"):
                    if isinstance(js, dict) and key in js and isinstance(js[key], list):
                        for row in js[key]:
                            yield row
                            seen += 1
                        url = js.get("next")
                        break
                else:
                    url = None
            if seen > 0:
                return  # on a bien streamé des lignes : fin
        except Exception as e:
            last_err = e
            continue
    # Si on tombe ici: aucune URL REST n'a marché
    if last_err:
        raise last_err
    raise RuntimeError("REST JSON introuvable")

# ---------------------------
# Itérateur universel
# ---------------------------
def iter_submissions(server_url: str, asset_uid: str, token: str, page_size=500):
    """
    Essaie OData → sinon bascule REST JSON.
    """
    # 1) OData
    try:
        for row in odata_iter_rows(server_url, asset_uid, token, page_size=page_size):
            yield row
        return
    except Exception:
        pass
    # 2) REST JSON
    for row in rest_iter_rows(server_url, asset_uid, token, page_size=page_size):
        yield row
