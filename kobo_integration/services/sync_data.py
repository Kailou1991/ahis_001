# kobo_integration/services/sync_data.py
from __future__ import annotations
import requests
from typing import Dict, Any

from kobo_integration.models import KoboForm
from kobo_integration.services.importer import upsert_one

def _auth_headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Token {token}"}

def _submissions_url(api_base: str, asset: str) -> str:
    # Essaie v2, sinon fallback ancien endpoint
    return f"{api_base}/api/v2/assets/{asset}/submissions/?format=json"

def sync_form_data(form: KoboForm, limit: int = 500) -> dict:
    """
    Télécharge les soumissions du formulaire Kobo et fait upsert pour chacune.
    Retourne un petit dict de stats.
    """
    api_base, token, verify = form.resolve_api()
    asset = form.asset_uid or form.xform_id_string
    url = _submissions_url(api_base, asset)

    r = requests.get(url, headers=_auth_headers(token), verify=verify, timeout=90)
    if r.status_code == 404:
        # fallback legacy (certaines instances)
        url = f"{api_base}/assets/{asset}/submissions/?format=json"
        r = requests.get(url, headers=_auth_headers(token), verify=verify, timeout=90)
    r.raise_for_status()
    data = r.json()

    if isinstance(data, dict) and "results" in data:
        rows = data["results"]
    else:
        rows = data if isinstance(data, list) else []

    total = created = updated = skipped = failed = 0
    for row in rows[:limit] if limit else rows:
        total += 1
        try:
            was_created, iid, changed = upsert_one(form, row)
            if was_created:
                created += 1
            else:
                if changed:
                    updated += 1
                else:
                    skipped += 1
        except Exception:
            failed += 1

    return {"total": total, "created": created, "updated": updated, "skipped": skipped, "failed": failed}
