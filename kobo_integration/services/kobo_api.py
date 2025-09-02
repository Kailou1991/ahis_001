from __future__ import annotations

import requests
from datetime import datetime
from typing import List, Optional, Dict, Any
import requests
from typing import Dict, Any, List

def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Token {token.strip()}", "Accept": "application/json"}

def test_connection(api_base: str, token: str, verify: bool = True) -> bool:
    url = f"{api_base.rstrip('/')}/assets/?format=json&limit=1"
    r = requests.get(url, headers=_headers(token), timeout=30, verify=verify)
    r.raise_for_status()
    return True

def fetch_submissions(api_base: str, asset_uid: str, token: str, limit: int = 100, verify: bool = True) -> List[Dict[str, Any]]:
    url = f"{api_base.rstrip('/')}/assets/{asset_uid}/submissions/?format=json&limit={limit}"
    r = requests.get(url, headers=_headers(token), timeout=60, verify=verify)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else data.get("results", [])

def fetch_schema(api_base: str, asset_uid: str, token: str, verify: bool = True) -> Dict[str, Any]:
    url = f"{api_base.rstrip('/')}/assets/{asset_uid}/?format=json"
    r = requests.get(url, headers=_headers(token), timeout=60, verify=verify)
    r.raise_for_status()
    return r.json()

# kobo_integration/services/kobo_api.py

def fetch_all_submissions(
    form,
    since: Optional[str] = None,
    page_size: int = 500,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Récupère toutes les soumissions pour un formulaire Kobo, en paginant.
    - Utilise form.resolve_api() pour (base, token, verify)
    - Si since est fourni (ISO 8601), filtre localement sur _submission_time > since
    """
    base, token, verify = form.resolve_api()
    uid = form.asset_uid or form.xform_id_string
    if not base or not uid:
        return []

    url = f"{base.rstrip('/')}/assets/{uid}/submissions/?format=json&page_size={page_size}"
    headers = {"Authorization": f"Token {token}"} if token else {}

    out: List[Dict[str, Any]] = []
    while url and (limit is None or len(out) < limit):
        r = requests.get(url, headers=headers, verify=verify, timeout=60)
        r.raise_for_status()
        data = r.json()

        if isinstance(data, dict) and "results" in data:
            batch = data.get("results", [])
            url = data.get("next")
        elif isinstance(data, list):  # certains déploiements renvoient une liste brute
            batch = data
            url = None
        else:
            break

        out.extend(batch)
        if limit is not None and len(out) >= limit:
            out = out[:limit]
            break

    # Filtrage "since" local (si fourni)
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except Exception:
            since_dt = None

        if since_dt is not None:
            def _parse_dt(v: Any):
                if not isinstance(v, str):
                    return None
                try:
                    return datetime.fromisoformat(v.replace("Z", "+00:00"))
                except Exception:
                    return None

            filtered = []
            for row in out:
                st = row.get("_submission_time") or row.get("submission_time")
                dt = _parse_dt(st)
                if dt and dt > since_dt:
                    filtered.append(row)
            out = filtered

    return out
