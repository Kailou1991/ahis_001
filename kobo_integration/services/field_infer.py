import re
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Set, Tuple

_NAME_RE = re.compile(r'[^a-z0-9_]+')

def sanitize_model_field(name: str, used: Set[str]) -> str:
    s = name.lower().replace('/', '_')
    s = _NAME_RE.sub('_', s).strip('_')
    if not s: s = 'field'
    if s[0].isdigit(): s = f'f_{s}'
    base, i = s, 2
    while s in used:
        s = f"{base}_{i}"; i += 1
    used.add(s)
    return s

def infer_dtype(v: Any, key: str) -> str:
    if v in (None, ""): return "string"
    if isinstance(v, bool): return "boolean"
    if isinstance(v, int): return "integer"
    if isinstance(v, float): return "decimal"
    if isinstance(v, list): return "string"  # select_multiple / repeat -> string (CSV/JSON)
    s = str(v)
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try: datetime.strptime(s, fmt); return "date"
        except: pass
    try:
        datetime.fromisoformat(s.replace("Z","+00:00")); return "datetime"
    except: pass
    if s.lower() in ("oui","non","yes","no","true","false","vrai","faux","1","0"):
        return "boolean"
    try: int(s); return "integer"
    except: 
        try: Decimal(s); return "decimal"
        except: pass
    if key.endswith("Geolocalisation_foyer") or key.endswith("_geolocation"):
        return "geo"
    return "string"

def flatten_keys(samples: List[Dict[str, Any]]) -> Dict[str, Any]:
    union: Dict[str, Any] = {}
    for p in samples:
        for k, v in p.items():
            union.setdefault(k, v)
    return union

def make_field_catalog(samples: List[Dict[str, Any]]) -> List[Tuple[str, str, str]]:
    union = flatten_keys(samples)
    used: Set[str] = set()
    catalog: List[Tuple[str, str, str]] = []
    for k, v in sorted(union.items()):
        if k in {"_attachments", "_notes", "_tags"}:
            continue
        model_field = sanitize_model_field(k, used)
        dtype = infer_dtype(v, k)
        catalog.append((k, model_field, dtype))
    return catalog
