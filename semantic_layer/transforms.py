# semantic_layer/transforms.py
from __future__ import annotations

import math
import re
from datetime import date, datetime
from typing import Any, Tuple

from django.utils.dateparse import parse_datetime, parse_date

# ---------- utilitaires ----------
NULL_STRINGS = {"", "null", "none", "na", "n/a", "nan", "nil", "-"}

def _is_nullish(x: Any) -> bool:
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    if isinstance(x, str) and x.strip().lower() in NULL_STRINGS:
        return True
    return False

# ---------- transforms de base ----------
def identity(x: Any) -> Any:
    return x

def to_date(val: Any) -> str | None:
    """
    Retourne une date ISO 'YYYY-MM-DD' ou None.
    Accepte:
      - date/datetime python
      - ISO 8601 avec Z, offset, millisecondes (ex: '2025-02-01T10:20:30.123Z')
      - 'YYYY-MM-DD' / 'YYYY/MM/DD' / 'DD/MM/YYYY'
    """
    if _is_nullish(val):
        return None

    if isinstance(val, date) and not isinstance(val, datetime):
        return val.isoformat()

    if isinstance(val, datetime):
        return val.date().isoformat()

    s = str(val).strip()

    # 1) django parsers
    dt = parse_datetime(s)
    if dt:
        return dt.date().isoformat()

    d = parse_date(s)
    if d:
        return d.isoformat()

    # 2) formats courants
    for fmt in ("%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except Exception:
            pass

    # 3) isoformat sans 'Z'
    try:
        return datetime.fromisoformat(s.replace("Z", "")).date().isoformat()
    except Exception:
        return None

_num_clean_re = re.compile(r"[^\d\.\-]")

def _normalize_number_str(s: str) -> str:
    """
    Normalise une chaîne numérique:
    - supprime espaces/nbsp
    - si ',' et '.' coexistent → ',' = séparateur de milliers → on enlève ','
    - si seulement ',' → on la transforme en '.'
    """
    s = s.strip().replace("\xa0", "").replace(" ", "")
    if "," in s and "." in s:
        s = s.replace(",", "")
    elif "," in s and "." not in s:
        s = s.replace(",", ".")
    return s

def to_number(val: Any) -> float | None:
    """
    Convertit en float. Gère booléens, '1 234,56', '1,234.56', etc.
    """
    if _is_nullish(val):
        return None
    if isinstance(val, bool):
        return 1.0 if val else 0.0
    if isinstance(val, (int, float)):
        return float(val)

    s = _normalize_number_str(str(val))
    try:
        return float(s)
    except Exception:
        s2 = _num_clean_re.sub("", s)
        try:
            return float(s2)
        except Exception:
            return None

def to_int(val: Any) -> int | None:
    n = to_number(val)
    return int(n) if n is not None else None

def to_bool(val: Any) -> bool | None:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in {"1", "true", "vrai", "yes", "oui", "y"}:
        return True
    if s in {"0", "false", "faux", "no", "non", "n"}:
        return False
    return None

# ---------- géolocalisation ----------
def _to_lat(x: Any) -> float | None:
    n = to_number(x)
    if n is None:
        return None
    return n if -90.0 <= n <= 90.0 else None

def _to_lon(x: Any) -> float | None:
    n = to_number(x)
    if n is None:
        return None
    return n if -180.0 <= n <= 180.0 else None

def _parse_geo(val: Any) -> Tuple[float | None, float | None]:
    """
    Accepte:
      - [lat, lon] / (lat, lon)
      - {'lat':..,'lon':..} ou {'latitude':..,'longitude':..} ou {'lng':..}
      - 'lat lon' ou 'lat,lon'
    """
    if val is None:
        return (None, None)

    if isinstance(val, (list, tuple)) and len(val) >= 2:
        return (_to_lat(val[0]), _to_lon(val[1]))

    if isinstance(val, dict):
        lat = val.get("lat") or val.get("latitude")
        lon = val.get("lon") or val.get("lng") or val.get("longitude")
        return (_to_lat(lat), _to_lon(lon))

    s = str(val).strip().replace(",", " ")
    parts = [p for p in s.split() if p]
    if len(parts) >= 2:
        return (_to_lat(parts[0]), _to_lon(parts[1]))

    return (None, None)

def split_geo_lat(val: Any) -> float | None:
    lat, _ = _parse_geo(val)
    return lat

def split_geo_lon(val: Any) -> float | None:
    _, lon = _parse_geo(val)
    return lon

# ---------- registre ----------
TRANSFORMS = {
    "identity": identity,
    "to_date": to_date,
    "to_number": to_number,
    "to_int": to_int,
    "to_bool": to_bool,
    "lat": split_geo_lat,
    "lon": split_geo_lon,
}
