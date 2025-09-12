# publishing/views.py
from __future__ import annotations

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, Http404, JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.core.cache import cache
from django.db.models import Prefetch
import re, csv, fnmatch, datetime
from decimal import Decimal
from io import BytesIO
from collections import defaultdict

# Matplotlib côté serveur (sans interface X)
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from openpyxl import Workbook

from .models import DatasetView, WidgetDef, ExportDef
from .forms import ViewWizardForm

# === semantic layer / kobo ===
from semantic_layer.models import WideRow, Dimension, FilterDef, Measure
from kobo_bridge.models import RawSubmission

# —— Formules / mesures/ dimensions calculées ——
from .compute import (
    prepare_query_metrics,
    append_computed_to_rows,
    extract_vars,
    extract_dims,
    eval_expr,
    _to_float,
)

# ----------------------------------------------------------------------
# Utilitaires généraux
# ----------------------------------------------------------------------
def _unique_slug(base_text: str) -> str:
    from django.utils.text import slugify
    base = slugify(base_text or "") or "view"
    pattern = rf"^{re.escape(base)}(-\d+)?$"
    existing = set(DatasetView.objects.filter(slug__regex=pattern).values_list("slug", flat=True))
    if base not in existing:
        return base
    i = 2
    while f"{base}-{i}" in existing:
        i += 1
    return f"{base}-{i}"

# valeurs d'une dim toujours sous forme de liste (gestion repeat)
def _iter_vals(dims: dict, key: str):
    v = (dims or {}).get(key)
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        return [x for x in v if x is not None]
    return [v]

# valeur "clé" hashable pour un group_dim (si liste -> "a|b|c")
def _key_value(dims: dict, key: str):
    v = (dims or {}).get(key)
    if isinstance(v, (list, tuple, set)):
        return "|".join(str(x) for x in v)
    return v

# lecture d'un champ dans un dict (supporte clés aplaties "A/B/C" et nested)
def _get_path(d, path: str):
    if d is None or path is None:
        return None
    if path in d:
        return d.get(path)
    cur = d
    for part in str(path).split("/"):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur

# ----------------------------------------------------------------------
# Assistant (création rapide de vue)
# ----------------------------------------------------------------------
def assistant_view(request):
    if request.method == "POST":
        form = ViewWizardForm(request.POST)
        if form.is_valid():
            ds = form.cleaned_data["dataset"]
            slug = _unique_slug(form.cleaned_data.get("slug") or form.cleaned_data.get("title") or "view")
            title = form.cleaned_data["title"]

            group_dims = [s.strip() for s in form.cleaned_data["default_group_dims"].split(",") if s.strip()]

            metrics = []
            for part in form.cleaned_data["default_metrics"].split(";"):
                part = part.strip()
                if not part:
                    continue
                if ":" in part:
                    code, agg = part.split(":", 1)
                    metrics.append({"code": code.strip(), "agg": (agg or "sum").strip().lower()})
                else:
                    metrics.append({"code": part.strip(), "agg": "sum"})

            vis_filters = [s.strip() for s in (form.cleaned_data.get("visible_filters") or "").split(",") if s.strip()]

            view = DatasetView.objects.create(
                dataset=ds, slug=slug, title=title,
                default_group_dims=group_dims, default_metrics=metrics,
                visible_filters=vis_filters, menu_title=title,
            )

            WidgetDef.objects.create(
                view=view, order_idx=1, type="table", enabled=True,
                config={"group_dims": group_dims, "metrics": metrics, "title": "Table"}
            )

            ExportDef.objects.create(
                view=view, name="Export XLSX", format="xlsx",
                config={"group_dims": group_dims, "metrics": metrics, "filters": {}},
                filename_pattern=f"AHIS_{slug}" + "_{date}"
            )
            return redirect("publishing:view_detail", slug=view.slug)
    else:
        form = ViewWizardForm()

    return render(request, "publishing/assistant_view.html", {"form": form})

# ----------------------------------------------------------------------
# Helpers parsing / normalisation
# ----------------------------------------------------------------------
_YMD_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")

def _parse_date_guess(val):
    """Accepte 'YYYY-MM-DD' | ISO datetime | 'DD/MM/YYYY' -> 'YYYY-MM-DD' ou None."""
    if not val:
        return None
    s = str(val).strip()
    m = _YMD_RE.search(s)
    if m:
        return m.group(1)
    try:
        if re.match(r"^\d{2}/\d{2}/\d{4}$", s):
            return datetime.datetime.strptime(s, "%d/%m/%Y").date().isoformat()
    except Exception:
        pass
    return None

def _normalize_values(raw_list):
    """Nettoie une liste + dédoublonne en conservant l'ordre."""
    bad = {"", "null", "none", "NULL", "None", "tous", "toutes", "— tous —", "— toutes —", "—", "-"}
    seen, out = set(), []
    for x in raw_list or []:
        s = str(x).strip()
        if s.lower() in bad:
            continue
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out

def _canonize_values_from_data(dataset, dim_code, raw_vals):
    """Ramène les valeurs vers celles réellement présentes (insensible casse + jokers)."""
    vals = _normalize_values(raw_vals)
    if not vals:
        return vals
    options = _distinct_values_for_dim_by_prefix(dataset, dim_code, prefix_filters={})
    lower_map = {o.lower(): o for o in options}

    canon = []
    for v in vals:
        if any(ch in v for ch in "*?"):
            matched = [o for o in options if fnmatch.fnmatch(o, v)]
            canon.extend(matched); continue
        o = lower_map.get(v.lower())
        canon.append(o if o else v)

    out, seen = [], set()
    for x in canon:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out

# Parseurs de config "table" (text -> listes)
def _parse_group_dims_text(s: str):
    return [d.strip() for d in (s or "").replace(";", ",").split(",") if d.strip()]

def _parse_metrics_text(s: str):
    out = []
    for part in (s or "").split(";"):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            code, agg = part.split(":", 1)
        else:
            code, agg = part, "sum"
        out.append({"code": code.strip(), "agg": agg.strip().lower()})
    return out

def _as_csv_text(v):
    """Normalise une valeur en texte CSV (pour champs free-text du widget, ex. lists/strings)."""
    if v is None:
        return ""
    if isinstance(v, (list, tuple, set)):
        return ",".join(str(x) for x in v)
    return str(v)

# ----------------------------------------------------------------------
# Plan de filtres générique (FilterDef) — compatible listes
# ----------------------------------------------------------------------
def _compile_filter_plan(dataset, filters: dict):
    """
    Compile une liste de tests à appliquer sur dims (WideRow ou item).
    Opérateurs supportés: in, eq, contains, between, gte, lte.
    Gère les champs scalaires ou listes (repeat).
    """
    filter_defs = FilterDef.objects.filter(dataset=dataset)
    defs_map = {f.code: f for f in filter_defs}
    tests = []
    coerce_cache = {}

    def _coerce(x):
        if x in coerce_cache:
            return coerce_cache[x]
        xs = "" if x is None else str(x)
        d = _parse_date_guess(xs)
        if d:
            result = ("D", d)
        else:
            try:
                result = ("N", Decimal(xs.replace(",", ".")))
            except Exception:
                result = ("S", xs)
        coerce_cache[x] = result
        return result

    for code, values in (filters or {}).items():
        fd = defs_map.get(code)
        dim_code = fd.dim_code if fd else code
        op = (fd.op if fd else "in").lower()

        vals = _normalize_values(values)
        if not vals:
            continue

        if op in ("in", "eq"):
            wanted = set(map(str, vals))
            eq_val = next(iter(wanted)) if op == "eq" else None
            def _t_in(dims, k=dim_code, wanted=wanted, eq_val=eq_val, is_eq=(op=="eq")):
                cand = [str(x) for x in _iter_vals(dims, k)]
                if not cand:
                    return False
                return any(c == eq_val for c in cand) if is_eq else any(c in wanted for c in cand)
            tests.append(_t_in)

        elif op == "contains":
            needles = [s.lower() for s in vals]
            def _t_contains(dims, k=dim_code, needles=needles):
                cand = [str(x).lower() for x in _iter_vals(dims, k)]
                return any(any(n in c for n in needles) for c in cand) if cand else False
            tests.append(_t_contains)

        elif op in ("between", "gte", "lte"):
            a = vals[0] if vals else None
            b = vals[1] if len(vals) > 1 else None

            if op == "between":
                def _t_between(dims, k=dim_code, A=a, B=b):
                    cand = _iter_vals(dims, k)
                    if not cand:
                        return False
                    for v in cand:
                        vv = _coerce(v)[1]
                        if A is not None and vv < _coerce(A)[1]: continue
                        if B is not None and vv > _coerce(B)[1]: continue
                        return True
                    return False
                tests.append(_t_between)

            elif op == "gte":
                def _t_gte(dims, k=dim_code, A=a):
                    cand = _iter_vals(dims, k)
                    return any(_coerce(v)[1] >= _coerce(A)[1] for v in cand) if cand else False
                tests.append(_t_gte)

            elif op == "lte":
                def _t_lte(dims, k=dim_code, B=b):
                    cand = _iter_vals(dims, k)
                    return any(_coerce(v)[1] <= _coerce(B)[1] for v in cand) if cand else False
                tests.append(_t_lte)

        else:
            wanted = set(map(str, vals))
            def _t_in2(dims, k=dim_code, wanted=wanted):
                cand = [str(x) for x in _iter_vals(dims, k)]
                return any(c in wanted for c in cand) if cand else False
            tests.append(_t_in2)

    return tests

def _row_passes(tests, dims):
    for t in tests:
        if not t(dims):
            return False
    return True

# ----------------------------------------------------------------------
# Détection d'usage de repeats (via Dimension.path / Measure.path)
# ----------------------------------------------------------------------
def _repeat_root(path: str):
    if not path or "/" not in path:
        return None
    return path.split("/", 1)[0]

def _collect_usage(dataset, group_dims, metrics, filters):
    dimensions = Dimension.objects.filter(dataset=dataset)
    measures = Measure.objects.filter(dataset=dataset)
    dmap = {d.code: d for d in dimensions}
    mmap = {m.code: m for m in measures}

    used_dim_codes = set(group_dims or [])
    used_dim_codes.update(filters.keys())

    repeat_roots = set()
    dim_paths = {}
    for code in used_dim_codes:
        d = dmap.get(code)
        if not d:
            continue
        dim_paths[code] = d.path
        r = _repeat_root(d.path)
        if r:
            repeat_roots.add(r)

    meas_paths = {}
    for m in metrics or []:
        code = m.get("code")
        mm = mmap.get(code)
        if not mm:
            continue
        meas_paths[code] = mm.path
        r = _repeat_root(mm.path)
        if r:
            repeat_roots.add(r)

    return {
        "dim_paths": dim_paths,
        "meas_paths": meas_paths,
        "repeat_roots": repeat_roots,
        "dims_map": dmap,
        "meas_map": mmap,
    }

# ----------------------------------------------------------------------
# Query base (sans explosion) + version avec repeat
# ----------------------------------------------------------------------
def _run_query_base(view, group_dims, metrics, filters, limit=100000, max_scan=500000):
    ds = view.dataset
    tests = _compile_filter_plan(ds, filters or {})
    rows_wide = WideRow.objects.filter(dataset=ds).values_list("dims", "meas")[:max_scan].iterator()

    agg_state = defaultdict(lambda: {
        "_dims": None,
        **{m['code']: {"sum": 0.0, "count": 0, "min": None, "max": None} for m in metrics}
    })
    gdim = list(group_dims or [])
    mlist = list(metrics or [])

    for dims, meas in rows_wide:
        if not isinstance(dims, dict) or not isinstance(meas, dict):
            continue
        if tests and not _row_passes(tests, dims):
            continue

        bkey_vals = [_key_value(dims, d) for d in gdim] if gdim else ["__ALL__"]
        bkey = tuple(bkey_vals)
        st = agg_state[bkey]
        if st["_dims"] is None:
            st["_dims"] = tuple(bkey_vals)

        for m in mlist:
            code = m.get("code")
            agg = (m.get("agg") or "sum").lower()
            slot = st[code]
            if agg == "count":
                slot["count"] += 1
                continue
            val = _to_float((meas or {}).get(code))
            if val is None:
                continue
            slot["sum"] += val
            slot["count"] += 1
            if slot["min"] is None or val < slot["min"]:
                slot["min"] = val
            if slot["max"] is None or val > slot["max"]:
                slot["max"] = val

    headers = gdim[:]
    for m in mlist:
        headers.append(f"{m.get('code')}__{(m.get('agg') or 'sum').lower()}")

    out_rows = []
    for st in agg_state.values():
        row = []
        if gdim:
            row.extend(list(st["_dims"]))
        for m in mlist:
            code = m.get("code")
            agg = (m.get("agg") or "sum").lower()
            slot = st.get(code, {"sum": 0.0, "count": 0, "min": None, "max": None})
            if agg == "sum":
                row.append(slot["sum"])
            elif agg == "count":
                row.append(slot["count"])
            elif agg == "avg":
                row.append((slot["sum"] / slot["count"]) if slot["count"] else 0.0)
            elif agg == "min":
                row.append(slot["min"] if slot["min"] is not None else 0.0)
            elif agg == "max":
                row.append(slot["max"] if slot["max"] is not None else 0.0)
            else:
                row.append(slot["sum"])
        out_rows.append(tuple(row))

    if gdim:
        out_rows.sort(key=lambda r: tuple("" if v is None else str(v) for v in r[:len(gdim)]))
    if isinstance(limit, int) and limit > 0:
        out_rows = out_rows[:limit]
    return headers, out_rows


def run_query_strict(view, group_dims, metrics, filters, limit=100000, max_scan=300000):
    # cache clé simple
    cache_key = f"query_{view.id}_{hash(str([group_dims, metrics, filters]))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ds = view.dataset
    usage = _collect_usage(ds, group_dims, metrics, filters)
    if not usage["repeat_roots"]:
        result = _run_query_base(view, group_dims, metrics, filters, limit, max_scan)
        cache.set(cache_key, result, 300)
        return result

    # un repeat à la fois (99% des cas)
    root = next(iter(usage["repeat_roots"]))
    tests = _compile_filter_plan(ds, filters or {})
    gdim = list(group_dims or [])
    mlist = list(metrics or [])

    meas_paths = usage["meas_paths"]
    per_item_metric = {m.get("code"): (meas_paths.get(m.get("code"), "") or "").startswith(root + "/") for m in mlist}

    rows_wide = WideRow.objects.filter(dataset=ds).values_list("dims", "meas", "source_id", "instance_id")[:max_scan].iterator()

    agg_state = defaultdict(lambda: {
        "_dims": None,
        **{m['code']: {"sum": 0.0, "count": 0, "min": None, "max": None} for m in metrics}
    })
    added_static = set()

    # batch payloads
    source_ids, instance_ids, wide_rows = [], [], []
    for dims, meas, src_id, inst_id in rows_wide:
        source_ids.append(src_id); instance_ids.append(inst_id)
        wide_rows.append((dims, meas, src_id, inst_id))

    payloads_map = {}
    if source_ids and instance_ids:
        for src_id, inst_id, payload in RawSubmission.objects.filter(
            source_id__in=source_ids, instance_id__in=instance_ids
        ).values_list("source_id", "instance_id", "payload"):
            payloads_map[(src_id, inst_id)] = payload

    for dims, meas, src_id, inst_id in wide_rows:
        if not isinstance(dims, dict) or not isinstance(meas, dict):
            continue
        payload = payloads_map.get((src_id, inst_id))

        # pas de payload ou pas de liste 'root' => ligne simple
        if not payload or root not in payload or not isinstance(payload[root], list):
            if tests and not _row_passes(tests, dims):
                continue
            bkey_vals = [_key_value(dims, d) for d in gdim] if gdim else ["__ALL__"]
            bkey = tuple(bkey_vals)
            st = agg_state[bkey]
            if st["_dims"] is None:
                st["_dims"] = tuple(bkey_vals)
            for m in mlist:
                code = m.get("code"); agg = (m.get("agg") or "sum").lower()
                slot = st[code]
                if agg == "count":
                    slot["count"] += 1; continue
                val = _to_float((meas or {}).get(code))
                if val is None: continue
                slot["sum"] += val; slot["count"] += 1
                if slot["min"] is None or val < slot["min"]:
                    slot["min"] = val
                if slot["max"] is None or val > slot["max"]:
                    slot["max"] = val
            continue

        # items du repeat
        items = payload[root]
        for it in items:
            dims_item = dict(dims)
            for dcode, dpath in usage["dim_paths"].items():
                if dpath and dpath.startswith(root + "/"):
                    dims_item[dcode] = _get_path(it, dpath)

            if tests and not _row_passes(tests, dims_item):
                continue

            bkey_vals = []
            for d in gdim:
                if usage["dim_paths"].get(d, "").startswith(root + "/"):
                    bkey_vals.append(dims_item.get(d))
                else:
                    bkey_vals.append(dims.get(d))
            bkey = tuple(bkey_vals) if bkey_vals else ("__ALL__",)
            st = agg_state[bkey]
            if st["_dims"] is None:
                st["_dims"] = tuple(bkey_vals)

            for m in mlist:
                code = m.get("code"); agg = (m.get("agg") or "sum").lower()
                slot = st[code]
                if agg == "count":
                    slot["count"] += 1; continue
                if per_item_metric.get(code, False):
                    raw = _get_path(it, meas_paths.get(code))
                    val = _to_float(raw)
                    if val is None: continue
                    slot["sum"] += val; slot["count"] += 1
                    if slot["min"] is None or val < slot["min"]:
                        slot["min"] = val
                    if slot["max"] is None or val > slot["max"]:
                        slot["max"] = val
                else:
                    marker = (src_id, inst_id, bkey, code)
                    if marker in added_static: continue
                    added_static.add(marker)
                    val = _to_float((meas or {}).get(code))
                    if val is None: continue
                    slot["sum"] += val; slot["count"] += 1
                    if slot["min"] is None or val < slot["min"]:
                        slot["min"] = val
                    if slot["max"] is None or val > slot["max"]:
                        slot["max"] = val

    headers = list(gdim or [])
    for m in mlist:
        headers.append(f"{m.get('code')}__{(m.get('agg') or 'sum').lower()}")

    out_rows = []
    for st in agg_state.values():
        row = []
        if gdim:
            row.extend(list(st["_dims"]))
        for m in mlist:
            code = m.get("code")
            agg = (m.get("agg") or "sum").lower()
            slot = st.get(code, {"sum": 0.0, "count": 0, "min": None, "max": None})
            if agg == "sum":
                row.append(slot["sum"])
            elif agg == "count":
                row.append(slot["count"])
            elif agg == "avg":
                row.append((slot["sum"] / slot["count"]) if slot["count"] else 0.0)
            elif agg == "min":
                row.append(slot["min"] if slot["min"] is not None else 0.0)
            elif agg == "max":
                row.append(slot["max"] if slot["max"] is not None else 0.0)
            else:
                row.append(slot["sum"])
        out_rows.append(tuple(row))

    if gdim:
        out_rows.sort(key=lambda r: tuple("" if v is None else str(v) for v in r[:len(gdim)]))
    if isinstance(limit, int) and limit > 0:
        out_rows = out_rows[:limit]

    result = (headers, out_rows)
    cache.set(cache_key, result, 300)
    return result

# ----------------------------------------------------------------------
# Cascade (sélecteurs dépendants) — compatible listes & repeats
# ----------------------------------------------------------------------
def _distinct_values_for_dim_by_prefix(dataset, dim_code: str, prefix_filters: dict, max_rows: int = 200000):
    cache_key = f"distinct_{dataset.id}_{dim_code}_{hash(str(prefix_filters))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    d = Dimension.objects.filter(dataset=dataset, code=dim_code).first()
    dpath = d.path if d else None
    root = _repeat_root(dpath) if d else None
    tests = _compile_filter_plan(dataset, prefix_filters or {})
    seen = set()

    if root:
        qs = WideRow.objects.filter(dataset=dataset).values_list("dims", "source_id", "instance_id")[:max_rows]
        source_ids, instance_ids, wide_rows = [], [], []
        for dims, src_id, inst_id in qs:
            source_ids.append(src_id); instance_ids.append(inst_id)
            wide_rows.append((dims, src_id, inst_id))

        payloads_map = {}
        if source_ids and instance_ids:
            for src_id, inst_id, payload in RawSubmission.objects.filter(
                source_id__in=source_ids, instance_id__in=instance_ids
            ).values_list("source_id", "instance_id", "payload"):
                payloads_map[(src_id, inst_id)] = payload

        for dims, src_id, inst_id in wide_rows:
            payload = payloads_map.get((src_id, inst_id))
            root_val = (payload or {}).get(root)

            if isinstance(root_val, list):
                # vrai repeat
                for it in root_val:
                    dims_item = dict(dims)
                    if dpath:
                        dims_item[dim_code] = _get_path(it, dpath)
                    if tests and not _row_passes(tests, dims_item):
                        continue
                    v = dims_item.get(dim_code)
                    if v is None:
                        continue
                    if isinstance(v, (list, tuple, set)):
                        for x in v:
                            sx = str(x).strip()
                            if sx: seen.add(sx)
                    else:
                        sx = str(v).strip()
                        if sx: seen.add(sx)
            else:
                # fallback non-repeat (groupe non répété)
                if tests and not _row_passes(tests, dims):
                    continue
                v = (dims or {}).get(dim_code)
                if v is None:
                    continue
                if isinstance(v, (list, tuple, set)):
                    for x in v:
                        sx = str(x).strip()
                        if sx: seen.add(sx)
                else:
                    sx = str(v).strip()
                    if sx: seen.add(sx)

        result = sorted(seen)
        cache.set(cache_key, result, 300)
        return result

    # pas de repeat
    qs = WideRow.objects.filter(dataset=dataset).values_list("dims", flat=True)[:max_rows]
    for dd in qs:
        if not isinstance(dd, dict):
            continue
        if tests and not _row_passes(tests, dd):
            continue
        v = dd.get(dim_code)
        if v is None:
            continue
        if isinstance(v, (list, tuple, set)):
            for x in v:
                sx = str(x).strip()
                if sx: seen.add(sx)
        else:
            sx = str(v).strip()
            if sx: seen.add(sx)
    result = sorted(seen)
    cache.set(cache_key, result, 300)
    return result



# ----------------------------------------------------------------------
# Parsing des filtres visibles (strictement ce que l'admin expose)
# ----------------------------------------------------------------------
def _parse_filters(request, view: DatasetView):
    filters = {}
    visible = list(view.visible_filters or [])
    for f in visible:
        vals = request.GET.getlist(f)
        if not vals:
            v = request.GET.get(f)
            if v is not None:
                vals = [v]
        vals = _canonize_values_from_data(view.dataset, f, vals)
        if vals:
            filters[f] = vals
    return filters

# ----------------------------------------------------------------------
# Vue principale (dashboard)
# ----------------------------------------------------------------------
def view_detail(request, slug):
    # Précharger les relations pour éviter les requêtes N+1
    view = get_object_or_404(
        DatasetView.objects.prefetch_related(
            Prefetch('widgets', queryset=WidgetDef.objects.filter(enabled=True).order_by('order_idx')),
            'exports'  # <— fixed related_name
        ),
        slug=slug
    )
    filters = _parse_filters(request, view)

    # cascade (options respectant les parents)
    visible_filters = [f for f in (view.visible_filters or [])]
    dim_order = visible_filters[:]
    filter_blocks, prefix = [], {}
    for code in dim_order:
        options = _distinct_values_for_dim_by_prefix(view.dataset, code, prefix)
        active = filters.get(code, [])
        filter_blocks.append({"code": code, "options": options, "active": active})
        if active:
            prefix[code] = active

    # --------- TABLE par défaut (compat) ---------
    base_metrics, comp_defs, var_agg_map = prepare_query_metrics(view, include_view_defaults=True)
    headers_raw, rows_raw = run_query_strict(
        view=view,
        group_dims=view.default_group_dims,
        metrics=base_metrics,
        filters=filters,
        limit=100000,
    )
    # computed (les colonnes gardent les codes)
    headers, rows = append_computed_to_rows(headers_raw, rows_raw, comp_defs, var_agg_map, filters=filters)

    # Hide/Only globaux de la vue (facultatif)
    only_param = (request.GET.get("only") or "").strip()
    hide_param = (request.GET.get("hide") or "").strip()
    if only_param:
        only_patterns = [s.strip() for s in only_param.split(",") if s.strip()]
        hide_patterns = []
    elif hide_param:
        only_patterns = []
        hide_patterns = [s.strip() for s in hide_param.split(",") if s.strip()]
    else:
        only_patterns = list(getattr(view, "table_only_cols", []) or [])
        hide_patterns = list(getattr(view, "table_hidden_cols", []) or [])

    def _compile_matcher(patterns):
        if not patterns:
            return lambda h: False
        testers = []
        for p in patterns:
            p = str(p)
            if any(ch in p for ch in ".^$[]()|+?\\"):
                try:
                    rx = re.compile(p)
                    testers.append(lambda h, rx=rx: bool(rx.search(h)))
                except re.error:
                    testers.append(lambda h, p=p: fnmatch.fnmatch(h, p))
            else:
                testers.append(lambda h, p=p: fnmatch.fnmatch(h, p))
        return lambda h: any(t(h) for t in testers)

    keep_idx = list(range(len(headers)))
    if only_patterns:
        match_only = _compile_matcher(only_patterns)
        keep_idx = [i for i, h in enumerate(headers) if match_only(h)]
    elif hide_patterns:
        match_hide = _compile_matcher(hide_patterns)
        keep_idx = [i for i, h in enumerate(headers) if not match_hide(h)]

    if keep_idx and len(keep_idx) < len(headers):
        headers = [headers[i] for i in keep_idx]
        rows = [[r[i] for i in keep_idx] for r in rows]

    # pagination de la table par défaut
    try:
        per = int(request.GET.get("per", 25))
    except Exception:
        per = 25
    per = max(5, min(per, 500))
    paginator = Paginator(rows, per)
    page = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    q = request.GET.copy()
    if "page" in q:
        q.pop("page")
    qs_no_page = q.urlencode()
    qs_all = request.META.get("QUERY_STRING", "")
    # on a préfetch 'exports', mais on garde l'ordre explicite et évite N+1
    exports = list(view.exports.all().order_by("id"))
    per_choices = [10, 25, 50, 100, 200]

    # ---------- KPI cards ----------
    kpi_widgets = list(view.widgets.filter(type="kpi_card", enabled=True).order_by("order_idx"))
    kpi_cards, kpi_max = [], 0.0
    if kpi_widgets:
        needed = {}
        for w in kpi_widgets:
            cfg = w.config or {}
            code = cfg.get("metric")
            agg = (cfg.get("agg") or "sum").lower()
            if any((c.get("code") or "") == code for c in comp_defs):
                cdef = next(c for c in comp_defs if (c.get("code") or "") == code)
                for var in extract_vars((cdef.get("expr") or ""), computed_codes=set(d.get("code") for d in comp_defs)):
                    if var not in needed:
                        needed[var] = var_agg_map.get(var) or "sum"
            else:
                if code:
                    needed[code] = agg

        metric_list = [{"code": c, "agg": a} for c, a in needed.items()]
        h2, r2 = run_query_strict(view=view, group_dims=[], metrics=metric_list, filters=filters, limit=1)
        rowmap = dict(zip(h2, (r2[0] if r2 else [])))

        def env_from_rowmap():
            env = {}
            for var, agg in var_agg_map.items():
                env[var] = rowmap.get(f"{var}__{agg}")
            for var, agg in needed.items():
                env[var] = rowmap.get(f"{var}__{agg}", env.get(var))
            return env

        for w in kpi_widgets:
            cfg = w.config or {}
            code = cfg.get("metric")
            agg = (cfg.get("agg") or "sum").lower()
            title = cfg.get("title") or code
            color = cfg.get("color") or "primary"

            val = None
            cdef = next((c for c in comp_defs if (c.get("code") or "") == code), None)
            if cdef:
                try:
                    v = eval_expr(cdef.get("expr") or "", env_from_rowmap(), row_dims=None, filters=filters)
                    if v is not None and cdef.get("round") is not None:
                        v = round(_to_float(v) or 0.0, int(cdef.get("round")))
                    val = v
                except Exception:
                    val = None
            else:
                val = rowmap.get(f"{code}__{agg}", None)

            vnum = _to_float(val) or 0.0
            kpi_max = max(kpi_max, vnum)
            kpi_cards.append({
                "title": title or code,
                "value": val if val is not None else 0,
                "value_num": vnum,
                "color": color,
                "metric": code,
                "agg": agg,
            })

        for c in kpi_cards:
            c["pct"] = int(round((c["value_num"] / kpi_max) * 100)) if kpi_max > 0 else 0

    # ---------- Graph widgets ----------
    widgets_graph = list(view.widgets.filter(enabled=True, type__in=["line", "bar"]).order_by("order_idx"))

    # ---------- Table widgets (multiples) ----------
    table_widgets = list(view.widgets.filter(enabled=True, type="table").order_by("order_idx"))
    tables = []
    if not table_widgets:
        # si aucun widget table, montrer au moins un tableau par défaut (mêmes données que la table de compat)
        tables.append({
            "id": 0,
            "title": "Table",
            "headers": headers,
            "rows": page_obj.object_list,
            "page_obj": page_obj,
        })
    else:
        for tw in table_widgets:
            cfg = tw.config or {}

            # NORMALISATION des champs éventuellement saisis comme listes
            group_dims = cfg.get("group_dims") or _parse_group_dims_text(_as_csv_text(cfg.get("group_dims_text")))
            metrics    = cfg.get("metrics")    or _parse_metrics_text(_as_csv_text(cfg.get("metrics_text")))
            per_table  = int(cfg.get("per") or 25)

            t_headers, t_rows = run_query_strict(
                view=view,
                group_dims=group_dims,
                metrics=metrics,
                filters=filters,
                limit=100000,
            )

            # keep/hide au niveau widget (peuvent être list OU string)
            only_p = _as_csv_text(cfg.get("only_cols")).strip()
            hide_p = _as_csv_text(cfg.get("hide_cols")).strip()

            if only_p or hide_p:
                def _compile_matcher_local(patterns_text: str):
                    if not patterns_text:
                        return lambda h: False
                    testers = []
                    for p in [s.strip() for s in patterns_text.split(",") if s.strip()]:
                        if any(ch in p for ch in ".^$[]()|+?\\"):
                            try:
                                rx = re.compile(p)
                                testers.append(lambda h, rx=rx: bool(rx.search(h)))
                            except re.error:
                                testers.append(lambda h, p=p: fnmatch.fnmatch(h, p))
                        else:
                            testers.append(lambda h, p=p: fnmatch.fnmatch(h, p))
                    return lambda h: any(t(h) for t in testers)

                keep_idx2 = list(range(len(t_headers)))
                if only_p:
                    match_only2 = _compile_matcher_local(only_p)
                    keep_idx2 = [i for i, h in enumerate(t_headers) if match_only2(h)]
                elif hide_p:
                    match_hide2 = _compile_matcher_local(hide_p)
                    keep_idx2 = [i for i, h in enumerate(t_headers) if not match_hide2(h)]

                if keep_idx2 and len(keep_idx2) < len(t_headers):
                    t_headers = [t_headers[i] for i in keep_idx2]
                    t_rows = [[r[i] for i in keep_idx2] for r in t_rows]

            paginator2 = Paginator(t_rows, max(5, min(per_table, 500)))
            page_num = request.GET.get(f"tpage_{tw.id}", 1)
            try:
                t_page = paginator2.page(page_num)
            except (PageNotAnInteger, EmptyPage):
                t_page = paginator2.page(1)

            tables.append({
                "id": tw.id,
                "title": (cfg.get("title") or "Tableau"),
                "headers": t_headers,
                "rows": t_page.object_list,
                "page_obj": t_page,
            })

    return render(
        request,
        "publishing/view_detail.html",
        {
            "view": view,
            # table de compat (toujours fournie)
            "headers": headers,
            "rows": page_obj.object_list,
            "page_obj": page_obj,
            "per": per,
            "per_choices": per_choices,
            # tables multiples
            "tables": tables,

            "visible_filters": visible_filters,
            "active_filters": filters,
            "filter_blocks": filter_blocks,
            "from_val": request.GET.get("from", ""),
            "to_val": request.GET.get("to", ""),
            "exports": exports,
            "qs": qs_all,
            "qs_no_page": qs_no_page,
            "kpi_cards": kpi_cards,
            "kpi_max": kpi_max,
            "widgets_graph": widgets_graph,
        },
    )

# ----------------------------------------------------------------------
# Endpoint JSON pour la cascade (options)
# ----------------------------------------------------------------------
def filter_options_json(request, slug, dim_code: str):
    view = get_object_or_404(DatasetView, slug=slug)
    order = [f for f in (view.visible_filters or [])]
    if dim_code not in order:
        return JsonResponse({"code": dim_code, "options": []})

    idx = order.index(dim_code)
    parents = order[:idx]
    prefix = {}
    for p in parents:
        vals = request.GET.getlist(p)
        if not vals:
            v = request.GET.get(p)
            if v is not None:
                vals = [v]
        vals = _canonize_values_from_data(view.dataset, p, vals)
        if vals:
            prefix[p] = vals

    options = _distinct_values_for_dim_by_prefix(view.dataset, dim_code, prefix)
    return JsonResponse({"code": dim_code, "options": options})

# ----------------------------------------------------------------------
# Widgets PNG (line/bar/kpi simple) — mêmes filtres via run_query_strict
# ----------------------------------------------------------------------
def widget_png(request, slug, widget_id: int):
    view = get_object_or_404(DatasetView, slug=slug)
    try:
        w = WidgetDef.objects.get(pk=widget_id, view=view)
    except WidgetDef.DoesNotExist:
        raise Http404("Widget introuvable")

    cfg = w.config or {}
    filters = _parse_filters(request, view)

    fig = plt.figure()
    ax = fig.gca()

    def _to_png(fig):
        buf = BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return HttpResponse(buf.getvalue(), content_type="image/png")

    if w.type == "kpi":
        metric = cfg.get("metric")
        agg = (cfg.get("agg") or "sum").lower()
        if not metric:
            ax.axis("off")
            plt.text(0.5, 0.5, "KPI non configuré", ha="center", va="center")
            return _to_png(fig)
        headers, rows = run_query_strict(
            view=view, group_dims=[], metrics=[{"code": metric, "agg": agg}], filters=filters, limit=1
        )
        val = rows[0][-1] if rows and len(rows[0]) else 0
        ax.axis("off")
        ax.text(0.5, 0.6, str(val), ha="center", va="center", fontsize=28)
        ax.text(0.5, 0.2, f"{agg.upper()} {metric}", ha="center", va="center", fontsize=10)
        return _to_png(fig)

    if w.type not in ("line", "bar"):
        ax.axis("off")
        plt.text(0.5, 0.5, f"Type non supporté: {w.type}", ha="center", va="center")
        return _to_png(fig)

    x = cfg.get("x")
    metric = cfg.get("metric")
    agg = (cfg.get("agg") or "sum").lower()

    if not x or not metric:
        ax.axis("off")
        plt.text(0.5, 0.5, "Configuration incomplète", ha="center", va="center")
        return _to_png(fig)

    base_metrics, comp_defs, var_agg_map = prepare_query_metrics(view, include_view_defaults=False)

    def _get_comp(code, kind=None):
        for c in comp_defs:
            if c["code"] == code and (kind is None or c.get("kind") == kind):
                return c
        return None

    comp_x = _get_comp(x, kind="dimension")
    comp_y = _get_comp(metric, kind="measure")

    if comp_x:
        dims_needed = list(extract_dims(comp_x.get("expr") or ""))
        if not dims_needed:
            ax.axis("off")
            plt.text(0.5, 0.5, "La dimension calculée n'utilise aucune DIM('...')", ha="center", va="center")
            return _to_png(fig)

        req_metrics = []
        if comp_y:
            vars_y = extract_vars(comp_y.get("expr") or "", computed_codes=set(d.get("code") for d in comp_defs))
            for v in sorted(vars_y):
                req_metrics.append({"code": v, "agg": var_agg_map.get(v, "sum")})
        else:
            req_metrics.append({"code": metric, "agg": agg})

        headers, rows = run_query_strict(
            view=view, group_dims=dims_needed, metrics=req_metrics, filters=filters, limit=100000
        )
        if not rows:
            ax.axis("off"); plt.text(0.5, 0.5, "Aucune donnée", ha="center", va="center"); return _to_png(fig)

        dim_idx = {d: headers.index(d) for d in dims_needed if d in headers}
        if comp_y:
            vars_y = extract_vars(comp_y.get("expr") or "", computed_codes=set(d.get("code") for d in comp_defs))
            meas_cols = {v: headers.index(f"{v}__{var_agg_map.get(v, 'sum')}") for v in vars_y if f"{v}__{var_agg_map.get(v, 'sum')}" in headers}
            if len(meas_cols) < len(vars_y):
                ax.axis("off"); plt.text(0.5, 0.5, "Colonnes manquantes pour la mesure calculée", ha="center", va="center"); return _to_png(fig)
        else:
            y_key = f"{metric}__{agg}"
            if y_key not in headers:
                ax.axis("off"); plt.text(0.5, 0.5, "Aucune donnée", ha="center", va="center"); return _to_png(fig)
            y_col = headers.index(y_key)

        bucket = {}
        for r in rows:
            dims_env = {d: r[dim_idx[d]] for d in dim_idx}
            env = {"_dims": dims_env}
            if comp_y:
                for v, cidx in meas_cols.items():
                    env[v] = r[cidx]
                y_val = _to_float(eval_expr(comp_y.get("expr") or "", env)) or 0.0
            else:
                y_val = _to_float(r[y_col]) or 0.0

            try:
                x_cat = eval_expr(comp_x.get("expr") or "", env)
            except Exception:
                x_cat = None
            if x_cat in (None, "", "null"):
                continue
            x_cat = str(x_cat)
            bucket[x_cat] = bucket.get(x_cat, 0.0) + y_val

        if not bucket:
            ax.axis("off"); plt.text(0.5, 0.5, "Aucune catégorie", ha="center", va="center"); return _to_png(fig)

        xs = sorted(bucket.keys())
        ys = [bucket[k] for k in xs]
        ax.plot(xs, ys) if w.type == "line" else ax.bar([str(v) for v in xs], ys)
        ax.set_title(cfg.get("title") or f"{metric} par {x}")
        ax.set_xlabel(x); ax.set_ylabel(metric); fig.autofmt_xdate()
        return _to_png(fig)

    # X normal
    if comp_y:
        vars_y = extract_vars(comp_y.get("expr") or "", computed_codes=set(d.get("code") for d in comp_defs))
        req_metrics = [{"code": v, "agg": var_agg_map.get(v, "sum")} for v in sorted(vars_y)]
        headers, rows = run_query_strict(view=view, group_dims=[x], metrics=req_metrics, filters=filters, limit=100000)
        if not rows:
            ax.axis("off"); plt.text(0.5, 0.5, "Aucune donnée", ha="center", va="center"); return _to_png(fig)
        xi = headers.index(x) if x in headers else 0
        xs, ys = [], []
        for r in rows:
            dims_env = {x: r[xi]}
            env = {"_dims": dims_env}
            for v in vars_y:
                cidx = headers.index(f"{v}__{var_agg_map.get(v, 'sum')}")
                env[v] = r[cidx]
            y_val = _to_float(eval_expr(comp_y.get("expr") or "", env)) or 0.0
            xs.append(r[xi]); ys.append(y_val)
        ax.plot(xs, ys) if w.type == "line" else ax.bar([str(v) for v in xs], ys)
        ax.set_title(cfg.get("title") or f"{metric} par {x}")
        ax.set_xlabel(x); ax.set_ylabel(metric); fig.autofmt_xdate()
        return _to_png(fig)

    headers, rows = run_query_strict(
        view=view, group_dims=[x], metrics=[{"code": metric, "agg": agg}], filters=filters, limit=100000
    )
    if not rows:
        ax.axis("off"); plt.text(0.5, 0.5, "Aucune donnée", ha="center", va="center"); return _to_png(fig)
    xi = 0
    y_key = f"{metric}__{agg}"
    if y_key not in headers:
        ax.axis("off"); plt.text(0.5, 0.5, "Aucune donnée", ha="center", va="center"); return _to_png(fig)
    yi = headers.index(y_key)
    xs = [r[xi] for r in rows]
    ys = [_to_float(r[yi]) or 0.0 for r in rows]
    ax.plot(xs, ys) if w.type == "line" else ax.bar([str(v) for v in xs], ys)
    ax.set_title(cfg.get("title") or f"{metric} par {x}")
    ax.set_xlabel(x); ax.set_ylabel(metric); fig.autofmt_xdate()
    return _to_png(fig)

# ----------------------------------------------------------------------
# Export — mêmes filtres que l'écran
# ----------------------------------------------------------------------
def export_view(request, slug, export_id):
    exp = get_object_or_404(ExportDef, pk=export_id, view__slug=slug)
    view = exp.view
    cfg = exp.config or {}

    eff_filters = _parse_filters(request, view)

    headers, rows = run_query_strict(
        view=view,
        group_dims=cfg.get("group_dims", view.default_group_dims),
        metrics=cfg.get("metrics", view.default_metrics),
        filters=eff_filters,
        limit=500000,
    )

    filename = (exp.filename_pattern or f"AHIS_{slug}_{{date}}").replace("{slug}", slug).replace("{date}", "today")

    if exp.format == "csv":
        resp = HttpResponse(content_type="text/csv")
        resp["Content-Disposition"] = f'attachment; filename="{filename}.csv"'
        w = csv.writer(resp); w.writerow(headers)
        for r in rows: w.writerow(list(r))
        return resp

    if exp.format == "xlsx":
        wb = Workbook(); ws = wb.active
        ws.append(headers)
        for r in rows: ws.append(list(r))
        bio = BytesIO(); wb.save(bio); bio.seek(0)
        resp = HttpResponse(
            bio.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        resp["Content-Disposition"] = f'attachment; filename="{filename}.xlsx"'
        return resp

    return HttpResponse("Format non supporté", status=400)
