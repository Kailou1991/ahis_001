# semantic_layer/services.py
import json
import re
import itertools
from typing import Iterable, Dict, Any, List, Tuple, Set, Optional
from django.db import transaction

from .models import DatasetLogical, Dimension, Measure, FilterDef, WideRow
from kobo_bridge.models import RawSubmission
from .transforms import TRANSFORMS

# ==================== Détection de types ====================
DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}([T\s]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+\-]\d{2}:\d{2})?)?$"
)

def _looks_like_date(v: Any) -> bool:
    if v is None or isinstance(v, (int, float)):
        return False
    s = str(v).strip()
    return 8 <= len(s) <= 35 and bool(DATE_RE.match(s))

def _looks_like_number(v: Any) -> bool:
    if v is None:
        return False
    if isinstance(v, (int, float)):
        return True
    if isinstance(v, str) and not v.strip():
        return False
    try:
        float(str(v).strip().replace(",", "."))
        return True
    except Exception:
        return False

# ==================== Helpers JSON tolérant ====================
def _strip_bom(text: str) -> str:
    return text.lstrip("\ufeff")

def _strip_trailing_commas(text: str) -> str:
    """
    Supprime TOUTES les virgules traînantes avant '}' ou ']' en dehors des chaînes.
    Exemple: {"a":1,} → {"a":1} ; [1,2,] → [1,2]
    """
    out: List[str] = []
    in_str = False
    escape = False

    def pop_ws_then_comma(buf: List[str]):
        i = len(buf) - 1
        while i >= 0 and buf[i].isspace():
            i -= 1
        if i >= 0 and buf[i] == ",":
            del buf[i]
        return buf

    for ch in text:
        if in_str:
            out.append(ch)
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue

        if ch == '"':
            in_str = True
            out.append(ch)
            continue

        if ch in ("]", "}"):
            pop_ws_then_comma(out)
            out.append(ch)
            continue

        out.append(ch)

    return "".join(out)

def safe_json_loads(text: str) -> Any:
    """Charge du JSON en nettoyant BOM + virgules traînantes (sans toucher aux chaînes)."""
    cleaned = _strip_bom(text)
    cleaned = _strip_trailing_commas(cleaned)
    return json.loads(cleaned)

def parse_json_payload(text: str) -> List[Dict[str, Any]]:
    """
    Accepte un tableau JSON ou un objet unique (encapsulé en liste).
    Tolère les virgules traînantes.
    """
    data = safe_json_loads(text)
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    raise ValueError("JSON inattendu: objet ou tableau attendu")

# ==================== Flatten helpers ====================
def _flatten_simple(row: Any, prefix: str = "") -> Iterable[Tuple[str, Any]]:
    """
    Aplati un dict Kobo en chemins 'a/b/c' → valeur. Ignore les listes.
    """
    if isinstance(row, dict):
        for k, v in row.items():
            nk = f"{prefix}/{k}" if prefix else k
            if isinstance(v, dict):
                yield from _flatten_simple(v, nk)
            elif isinstance(v, list):
                continue
            else:
                yield nk, v
    else:
        yield prefix, row

def _merge_maps(a: Dict[str, Any], b: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(a)
    out.update(b)
    return out

def _flatten_rows_with_repeats(obj: Any, repeat_set: Set[str], prefix: str = "") -> List[Dict[str, Any]]:
    """
    Renvoie une LISTE de lignes aplaties (dict chemin->valeur),
    en dépliant les LISTES pour les chemins de répétition choisis (repeat_set).
    Plusieurs répétitions → produit cartésien (attention au volume).
    """
    rows = [dict()]
    if isinstance(obj, dict):
        for k, v in obj.items():
            nk = f"{prefix}/{k}" if prefix else k
            if isinstance(v, dict):
                child_rows = _flatten_rows_with_repeats(v, repeat_set, nk)
                rows = [_merge_maps(r, cr) for r, cr in itertools.product(rows, child_rows)]
            elif isinstance(v, list):
                if nk in repeat_set and v:
                    expanded_rows = []
                    for base in rows:
                        for item in v:
                            child_rows = _flatten_rows_with_repeats(item, repeat_set, nk)
                            for cr in child_rows:
                                expanded_rows.append(_merge_maps(base, cr))
                    rows = expanded_rows
                else:
                    continue
            else:
                for r in rows:
                    r[nk] = v
    else:
        for r in rows:
            r[prefix] = obj
    return rows

# ==================== Codes & labels ====================
def _code_from_path(path: str) -> str:
    last = path.split("/")[-1]
    code = re.sub(r"[^0-9A-Za-z_]", "_", last).strip("_")
    return code or "field"

def _label_from_code(code: str) -> str:
    return code.replace("_", " ").title()

def _to_snake(s: str) -> str:
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"[^0-9A-Za-z_]", "_", s).strip("_")
    return s.lower()

def _to_kebab(s: str) -> str:
    return _to_snake(s).replace("_", "-")

def _to_camel(s: str) -> str:
    parts = _to_snake(s).split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])

def _to_pascal(s: str) -> str:
    return "".join(p.capitalize() for p in _to_snake(s).split("_"))

def _apply_case(code: str, case: str) -> str:
    case = (case or "keep").lower()
    if case == "snake":  return _to_snake(code)
    if case == "kebab":  return _to_kebab(code)
    if case == "camel":  return _to_camel(code)
    if case == "pascal": return _to_pascal(code)
    return code

# ==================== Détection des répétitions ====================
def detect_repeat_candidates(records: List[Dict[str, Any]], sample: int = 100) -> List[str]:
    """
    Liste des chemins 'a/b/c' où la valeur rencontrée est une LISTE d'objets (répétition Kobo).
    """
    candidates: Set[str] = set()
    for r in records[:sample]:
        stack = [("", r)]
        while stack:
            prefix, obj = stack.pop()
            if isinstance(obj, dict):
                for k, v in obj.items():
                    nk = f"{prefix}/{k}" if prefix else k
                    if isinstance(v, dict):
                        stack.append((nk, v))
                    elif isinstance(v, list):
                        if v and isinstance(v[0], dict):
                            candidates.add(nk)
    return sorted(candidates)

# ==================== Analyse JSON → suggestions ====================
def analyze_json_records(
    records: List[Dict[str, Any]],
    sample: int = 200,
    expand_repeat_paths: Optional[List[str]] = None,
    rename_map: Optional[Dict[str, str]] = None,
    code_case: str = "keep",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Détecte Dimensions/Mesures/Filtres.
    - expand_repeat_paths: chemins à DÉPLIER (répétitions).
    - rename_map: { chemin_ou_code_source: code_cible } pour imposer des codes.
    - code_case: 'keep'|'snake'|'kebab'|'camel'|'pascal'
    """
    expand_set = set(expand_repeat_paths or [])
    rename_map = rename_map or {}

    type_stats: Dict[str, Dict[str, int]] = {}
    for r in records[:sample]:
        flat_rows = (
            _flatten_rows_with_repeats(r, expand_set)
            if expand_set else
            [dict(_flatten_simple(r))]
        )
        for fr in flat_rows:
            for path, val in fr.items():
                if val in (None, "", []):
                    continue
                s = type_stats.setdefault(path, {"num": 0, "date": 0, "text": 0})
                if _looks_like_date(val):
                    s["date"] += 1
                elif _looks_like_number(val):
                    s["num"] += 1
                else:
                    s["text"] += 1

    dims, meas = [], []
    known_dim_names = {"region", "cercle", "commune", "antigene", "espece", "maladie"}

    for path, stat in sorted(type_stats.items()):
        last = path.split("/")[-1]
        last_l = last.lower()

        code_src = rename_map.get(path) or rename_map.get(last) or last
        code = _apply_case(_code_from_path(code_src), code_case)
        label = _label_from_code(code)

        # dates
        if stat["date"] > 0 or last_l.startswith("date") or last_l.endswith("date") or last_l in {"_submission_time", "start", "end"}:
            dims.append(dict(
                code=code, label=label, path=path,
                dtype="date", transform="to_date", is_time=True,
            ))
            continue

        # dimensions connues
        if last_l in known_dim_names:
            dims.append(dict(
                code=code, label=label, path=path,
                dtype="code", is_time=False,
            ))
            continue

        # mesures (numériques), éviter IDs/UUID/téléphones
        if stat["num"] > 0 and not last_l.startswith("_") and "uuid" not in last_l and last_l != "id":
            if "telephone" in last_l or "phone" in last_l:
                continue
            meas.append(dict(
                code=code, label=label, path=path,
                transform="to_number", default_agg="sum",
            ))

    # Filtres proposés
    filters = []
    time_dim = next((d for d in dims if d.get("is_time")), None)
    if time_dim:
        filters.append(dict(code="periode", label="Période", dim_code=time_dim["code"], op="between"))
    for cand in ("region", "cercle", "commune", "antigene", "espece", "maladie"):
        norm = _apply_case(cand, code_case)
        if any(d["code"] == norm for d in dims):
            filters.append(dict(code=norm, label=_label_from_code(cand), dim_code=norm, op="in"))

    return {"dimensions": dims, "measures": meas, "filters": filters}

# ==================== Création idempotente du mapping ====================
@transaction.atomic
def create_mapping_from_suggestions(dataset: DatasetLogical, sugg: Dict[str, List[Dict[str, Any]]]) -> Dict[str, int]:
    c_dim = c_mea = c_fil = 0

    for d in sugg.get("dimensions", []):
        _, created = Dimension.objects.update_or_create(
            dataset=dataset, code=d["code"],
            defaults=dict(
                label=d.get("label") or d["code"],
                path=d["path"],
                dtype=d.get("dtype") or "code",
                transform=d.get("transform") or "",
                is_time=bool(d.get("is_time")),
            )
        )
        c_dim += int(created)

    for m in sugg.get("measures", []):
        _, created = Measure.objects.update_or_create(
            dataset=dataset, code=m["code"],
            defaults=dict(
                label=m.get("label") or m["code"],
                path=m["path"],
                transform=m.get("transform") or "to_number",
                default_agg=m.get("default_agg") or "sum",
            )
        )
        c_mea += int(created)

    for f in sugg.get("filters", []):
        _, created = FilterDef.objects.update_or_create(
            dataset=dataset, code=f["code"],
            defaults=dict(
                label=f.get("label") or f["code"],
                dim_code=f.get("dim_code"),
                op=f.get("op") or "in",
            )
        )
        c_fil += int(created)

    return {"dimensions": c_dim, "measures": c_mea, "filters": c_fil}

# ==================== Rebuild WideRows (LIST-aware) ====================
def _deep_collect_by_suffix(node: Any, suffix: str, last: str) -> List[Any]:
    """
    Parcourt récursivement dict/list et collecte les valeurs dont la clé:
      - est exactement 'suffix' (ex: 'a/b/c')
      - se termine par '/suffix'
      - se termine par '/last' (ex: juste 'c'), utile si les parents varient
    """
    found = []
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(k, str):
                if k == suffix or k.endswith("/" + suffix) or k.endswith("/" + last) or k == last:
                    # Si v est un conteneur, on retourne v tel quel (on laissera l'appelant décider)
                    found.append(v)
            # continuer à descendre
            found.extend(_deep_collect_by_suffix(v, suffix, last))
    elif isinstance(node, list):
        for it in node:
            found.extend(_deep_collect_by_suffix(it, suffix, last))
    return found


def _extract_all(payload: dict, path: str) -> List[Any]:
    """
    Retourne toutes les valeurs au bout de 'a/b/c' en traversant dicts & listes.

    Stratégie:
      1) Parcours hiérarchique classique (segment par segment).
      2) À chaque niveau dict: essaie aussi une clé *exacte* 'reste/du/chemin'.
      3) À chaque niveau dict: essaie une clé qui *se termine par* 'reste/du/chemin'.
      4) Si rien: fallback racine (exact + suffixe).
      5) Si toujours rien: **scan profond** qui collecte toute clé finissant par
         le *chemin complet* ou seulement par le *dernier segment* (ex.: 'c').
    """
    segs = path.split("/")
    last = segs[-1]

    def rec(node, i):
        if node is None:
            return []
        if i == len(segs):
            return [node]

        key = segs[i]
        # dict
        if isinstance(node, dict):
            # 1) hiérarchique
            if key in node:
                return rec(node.get(key), i + 1)

            # 2) clé "aplatie" = tout le reste du chemin
            remainder = "/".join(segs[i:])
            if remainder in node:
                return rec(node.get(remainder), len(segs))

            # 3) suffixe '.../remainder'
            out = []
            for k, v in node.items():
                if isinstance(k, str) and k.endswith(remainder):
                    out.extend(rec(v, len(segs)))
            if out:
                return out

            # 4) sinon, on tente de descendre dans chaque valeur
            out2 = []
            for v in node.values():
                out2.extend(rec(v, i))
            return out2

        # list → agréger
        if isinstance(node, list):
            out = []
            for it in node:
                out.extend(rec(it, i))
            return out

        # feuille
        return []

    vals = rec(payload, 0)
    if vals:
        return vals

    # 4) fallback racine (exact + suffixe)
    v = payload.get(path)
    if v is not None:
        return [v]
    out = []
    for k, val in payload.items():
        if isinstance(k, str) and (k == path or k.endswith("/" + path) or k.endswith("/" + last) or k == last):
            out.append(val)
    if out:
        return out

    # 5) **scan profond**: n'importe où dans l'arbre
    deep = _deep_collect_by_suffix(payload, path, last)
    return deep

def _first_non_null(vals: List[Any]) -> Any:
    for v in vals:
        if v not in (None, "", []):
            return v
    return None

def _to_float_or_none(v: Any) -> Optional[float]:
    if v in (None, "", []):
        return None
    try:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", ".")
        return float(s)
    except Exception:
        return None

def _apply(val, name):
    fn = TRANSFORMS.get(name or "identity")
    return fn(val) if fn else val

@transaction.atomic
def rebuild_widerows_for_dataset(ds: DatasetLogical):
    """
    Projette TOUTES les RawSubmission de la source du dataset en WideRow
    selon Dimensions / Measures déclarées par l'admin.

    Règles:
    - Dimensions : prend la **première valeur non nulle** trouvée.
    - Mesures    : si plusieurs valeurs (répétitions), on **applique transform** à chaque feuille
                   puis on **somme** les valeurs numériques ; sinon on garde la 1ère valeur transformée.
    Idempotent par (dataset, instance_id).
    """
    dims_cfg = list(ds.dimensions.all())
    meas_cfg = list(ds.measures.all())
    src = ds.source

    for raw in RawSubmission.objects.filter(source=src):
        payload = raw.payload or {}
        dims: Dict[str, Any] = {}
        meas: Dict[str, Any] = {}

        # Dimensions
        for d in dims_cfg:
            vals = _extract_all(payload, d.path)
            val = _first_non_null(vals)
            dims[d.code] = _apply(val, d.transform)

        # Mesures
        for m in meas_cfg:
            vals = _extract_all(payload, m.path)
            if not vals:
                meas[m.code] = None
                continue

            transformed = [_apply(v, m.transform) for v in vals]

            nums = [_to_float_or_none(v) for v in transformed]
            nums = [x for x in nums if x is not None]
            if nums:
                meas[m.code] = sum(nums)
            else:
                meas[m.code] = _first_non_null(transformed)

        WideRow.objects.update_or_create(
            dataset=ds,
            instance_id=raw.instance_id,
            defaults=dict(
                source=src,
                submitted_at=raw.submitted_at,
                dims=dims,
                meas=meas,
            )
        )
