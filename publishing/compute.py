# publishing/compute.py
from __future__ import annotations

import math
import re
from typing import Dict, List, Tuple, Iterable, Any, Set

# -------------------------------
# Utilitaires
# -------------------------------

def _to_float(v) -> float | None:
    if v is None:
        return None
    try:
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace(",", ".")
        if s == "" or s.lower() in {"nan", "none", "null"}:
            return None
        return float(s)
    except Exception:
        return None


# -------------------------------
# Extraction variables / dimensions
# -------------------------------

# Mots/fonctions réservés que l'on ne doit pas traiter comme variables
_RESERVED: Set[str] = {
    "IF", "IN", "DIM", "NUM",
    "AND", "OR", "NOT",
    "TRUE", "FALSE", "NULL",
    # Fonctions arithmétiques supportées par l'évaluateur
    "ABS", "MIN", "MAX", "ROUND", "FLOOR", "CEIL", "COALESCE",
}

# Retirer les littéraux string pour éviter de récupérer du faux texte comme variable
_STR_RE = re.compile(r"'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\"")

def _strip_strings(expr: str) -> str:
    return _STR_RE.sub("''", expr or "")

def extract_vars(expr: str, computed_codes: Set[str] | None = None) -> Set[str]:
    """
    Retourne l'ensemble des identifiants susceptibles d'être des variables (mesures physiques)
    dans l'expression. On ignore:
      - les codes déjà calculés (computed_codes)
      - les mots/fonctions réservés (insensible à la casse)
    """
    if not expr:
        return set()
    s = _strip_strings(expr)
    tokens = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", s)
    comp = set((computed_codes or set()))
    out = set()
    for w in tokens:
        wu = w.upper()
        if w in comp:
            continue
        if wu in _RESERVED:
            continue
        out.add(w)
    return out


# DIM('code') -> extraction des codes de dimensions référencés
_DIM_RE = re.compile(r"""DIM\(\s*['"](?P<code>[^'"]+)['"]\s*\)""", re.IGNORECASE)

def extract_dims(expr: str):
    """Retourne l'ensemble des codes passés à DIM('code') dans l'expression."""
    if not expr:
        return set()
    return {m.group("code") for m in _DIM_RE.finditer(expr or "")}


# -------------------------------
# Évaluateur
# -------------------------------

class Multi:
    """Plusieurs valeurs possibles d'une dimension (filtres multiples)."""
    __slots__ = ("items", "_set")
    def __init__(self, items: Iterable[Any]):
        cleaned = [str(x) for x in (items or []) if x not in (None, "", "null")]
        self.items = cleaned
        self._set = set(cleaned)
    def intersects(self, seq: Iterable[Any]) -> bool:
        for s in (seq or []):
            if str(s) in self._set:
                return True
        return False

def eval_expr(expr: str,
              env: Dict[str, Any],
              row_dims: Dict[str, Any] | None = None,
              filters: Dict[str, List[Any]] | None = None) -> Any:
    """
    Évalue une expression de KPI/mesure/dimension calculée.

    - DIM('code') :
        * renvoie la valeur de la dimension pour la ligne (row_dims) si présente
        * sinon, renvoie la/les valeur(s) actives du filtre correspondant :
            - 0 valeur -> None
            - 1 valeur -> "value"
            - n valeurs -> Multi([...])  (pour IN)
    - IN(a, b) :
        * si a est Multi -> test d'intersection
        * sinon -> a in b (b peut être list/tuple/set)
    - NUM(x) :
        * conversion numérique tolérante (retourne None si vide/invalide)
    - Fonctions autorisées: ABS, MIN, MAX, ROUND, FLOOR, CEIL, COALESCE
    """
    row_dims = row_dims or {}
    filters = filters or {}

    def _DIM(code: str):
        # priorité à la valeur de ligne si non vide
        if code in row_dims and row_dims.get(code) not in (None, "", "null"):
            return row_dims.get(code)
        vals = [v for v in (filters.get(code) or []) if v not in (None, "", "null")]
        if not vals:
            return None
        if len(vals) == 1:
            return vals[0]
        return Multi(vals)

    def _IN(a, b):
        if b is None:
            return False
        if isinstance(a, Multi):
            # b peut être une liste, un set, un tuple
            if isinstance(b, (list, tuple, set)):
                return a.intersects(b)
            # si b est un scalaire, on teste l'appartenance simple
            return str(b) in a._set
        # cas scalaire
        if isinstance(b, (list, tuple, set)):
            return a in b
        return a == b

    def _NUM(x):
        return _to_float(x)

    def _IF(cond, a, b):
        return a if bool(cond) else b

    def _COALESCE(*args):
        for v in args:
            if v not in (None, "", "null"):
                return v
        return None

    safe_globals = {
        "__builtins__": {},  # sandbox
        # logique
        "IF": _IF, "IN": _IN, "DIM": _DIM, "NUM": _NUM,
        "TRUE": True, "FALSE": False, "NULL": None,
        # fonctions math sûres
        "ABS": lambda x: abs(_to_float(x) or 0.0),
        "MIN": lambda *xs: min([_to_float(v) or 0.0 for v in xs]) if xs else 0.0,
        "MAX": lambda *xs: max([_to_float(v) or 0.0 for v in xs]) if xs else 0.0,
        "ROUND": lambda x, n=0: round(_to_float(x) or 0.0, int(n or 0)),
        "FLOOR": lambda x: math.floor(_to_float(x) or 0.0),
        "CEIL": lambda x: math.ceil(_to_float(x) or 0.0),
        "COALESCE": _COALESCE,
    }
    local_env = dict(env or {})

    try:
        return eval(expr, safe_globals, local_env)
    except Exception:
        return None


# -------------------------------
# Préparation des métriques
# -------------------------------

def _dedup_metrics(metrics: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    out = []
    for m in metrics or []:
        c = (m.get("code") or "").strip()
        a = (m.get("agg") or "sum").strip().lower()
        if not c:
            continue
        key = (c, a)
        if key in seen:
            continue
        seen.add(key)
        out.append({"code": c, "agg": a})
    return out

def prepare_query_metrics(view, include_view_defaults: bool = True
                          ) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]], Dict[str, str]]:
    """
    Construit:
      - base_metrics : mesures physiques à requêter (défauts + dépendances des calculées)
      - comp_defs    : définitions de mesures/dimensions calculées (view.computed_metrics[*])
      - var_agg_map  : mapping {variable -> agg} pour évaluer les calculées

    NB: la normalisation code/libellé est gérée côté view (voir views.py),
    ici on manipule uniquement des codes.
    """
    comp_defs = list(getattr(view, "computed_metrics_cache", None)
                     or getattr(view, "computed_metrics", None)
                     or [])

    var_agg_map: Dict[str, str] = {}
    default_list = list(view.default_metrics or [])
    for m in default_list:
        c = (m.get("code") or "").strip()
        a = (m.get("agg") or "sum").strip().lower()
        if c and c not in var_agg_map:
            var_agg_map[c] = a

    needed_vars: Set[str] = set()
    comp_codes = {c.get("code") for c in comp_defs if c.get("code")}
    for c in comp_defs:
        if (c.get("kind") or "measure") == "measure":
            expr = c.get("expr") or ""
            needed_vars.update(extract_vars(expr, computed_codes=comp_codes))

    base_metrics: List[Dict[str, str]] = []
    if include_view_defaults:
        base_metrics.extend(default_list)
    for v in sorted(needed_vars):
        base_metrics.append({"code": v, "agg": var_agg_map.get(v, "sum")})
    base_metrics = _dedup_metrics(base_metrics)
    return base_metrics, comp_defs, var_agg_map


# -------------------------------
# Post-traitement lignes: computed + roll-up
# -------------------------------

def append_computed_to_rows(headers: List[str],
                            rows: List[Iterable[Any]],
                            comp_defs: List[Dict[str, Any]],
                            var_agg_map: Dict[str, str],
                            filters: Dict[str, List[Any]] | None = None
                            ) -> Tuple[List[str], List[List[Any]]]:
    """
    Ajoute au tableau les colonnes calculées (dimensions + mesures),
    en rendant disponibles:
      - row_dims : dict des dimensions présentes dans la ligne (colonnes sans '__')
      - env      : dict {var (mesure physique) -> valeur} d'après var_agg_map
      - filters  : filtres actifs (pour DIM('...'))
    """
    filters = filters or {}

    # Dimensions présentes (heuristique: colonnes sans "__")
    dim_idx = [i for i, h in enumerate(headers) if "__" not in h]
    dim_names = [headers[i] for i in dim_idx]

    # Mesures de base disponibles
    meas_cols: Dict[str, int] = {}
    for var, agg in var_agg_map.items():
        key = f"{var}__{agg}"
        if key in headers:
            meas_cols[var] = headers.index(key)

    comp_dims = [c for c in comp_defs if (c.get("kind") or "measure") == "dimension"]
    comp_meas = [c for c in comp_defs if (c.get("kind") or "measure") == "measure"]

    new_headers = list(headers)
    for c in comp_dims:
        code = c.get("code")
        if code and code not in new_headers:
            new_headers.append(code)
    for c in comp_meas:
        code = c.get("code")
        if code and code not in new_headers:
            new_headers.append(code)

    new_rows: List[List[Any]] = []
    for r in rows:
        r = list(r)
        row_dims = {dim_names[i]: r[dim_idx[i]] for i in range(len(dim_idx))}
        env = {var: r[col] for var, col in meas_cols.items()}

        # Dimensions calculées
        dim_results = {}
        for c in comp_dims:
            code = c.get("code")
            expr = c.get("expr") or ""
            try:
                v = eval_expr(expr, env, row_dims=row_dims, filters=filters)
            except Exception:
                v = None
            dim_results[code] = v
        for c in comp_dims:
            r.append(dim_results.get(c.get("code")))

        # Mesures calculées
        for c in comp_meas:
            expr = c.get("expr") or ""
            val = None
            try:
                v = eval_expr(expr, env, row_dims=row_dims, filters=filters)
                rnd = c.get("round", None)
                if v is not None and rnd is not None:
                    v = round(_to_float(v) or 0.0, int(rnd))
                val = v
            except Exception:
                val = None
            r.append(val)

        new_rows.append(r)

    return new_headers, new_rows


# -------------------------------
# Aide roll-up (ré-agrégation)
# -------------------------------

def rollup_sum(headers: List[str],
               rows: List[List[Any]],
               keep_dims: List[str],
               drop_dims: List[str],
               comp_measures_codes: Set[str]) -> Tuple[List[str], List[List[Any]]]:
    """
    Regroupe les lignes par keep_dims et somme toutes les colonnes de mesures
    (colonnes avec '__' ou codes dans comp_measures_codes). Supprime drop_dims.
    """
    # indices
    keep_dims = [d for d in keep_dims if d in headers]
    drop_dims = [d for d in drop_dims if d in headers]
    keep_idx = [headers.index(d) for d in keep_dims]
    drop_idx = set(headers.index(d) for d in drop_dims)

    # colonnes "mesure-like"
    measure_idx = set(
        i for i, h in enumerate(headers)
        if ("__" in h) or (h in comp_measures_codes)
    )
    # colonnes à conserver à la fin (dims conservées + mesures)
    final_idx = keep_idx + [i for i in range(len(headers)) if i not in keep_idx and i not in drop_idx and i in measure_idx]
    final_headers = [headers[i] for i in final_idx]

    # agrégation
    buckets = {}  # key(tuple) -> agg list
    for r in rows:
        key = tuple(r[i] for i in keep_idx) if keep_idx else ("__ALL__",)
        agg = buckets.get(key)
        if agg is None:
            # init
            agg = []
            for i in final_idx:
                if i in keep_idx:
                    agg.append(r[i])
                else:
                    f = _to_float(r[i])
                    agg.append(f if f is not None else 0.0)
            buckets[key] = agg
        else:
            # somme sur mesures
            for j, i in enumerate(final_idx):
                if i in keep_idx:
                    continue
                f = _to_float(r[i])
                agg[j] = (agg[j] or 0.0) + (f or 0.0)

    out_rows = list(buckets.values())
    return final_headers, out_rows
