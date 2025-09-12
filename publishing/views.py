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

def _pick_date_dim(dataset):
    try:
        fdefs = list(FilterDef.objects.filter(dataset=dataset))
        by_code = {f.code: f for f in fdefs}
        for k in ("from", "du"):
            if k in by_code and by_code[k].dim_code:
                return by_code[k].dim_code
        for k in ("to", "au"):
            if k in by_code and by_code[k].dim_code:
                return by_code[k].dim_code
    except Exception:
        pass
    try:
        dims = list(Dimension.objects.filter(dataset=dataset))
        date_like = [d for d in dims if str(getattr(d, "dtype", "")).lower() in {"date","datetime","timestamp"}]
        if date_like:
            return date_like[0].code
        preferred = ["DateVaccination","date_vaccination","date","Date","submissionTime","end","start","timestamp"]
        lower_map = {d.code.lower(): d.code for d in dims}
        for p in preferred:
            if p.lower() in lower_map:
                return lower_map[p.lower()]
    except Exception:
        pass
    return None

def _resolve_dim_alias(dataset, code: str) -> str:
    if not code:
        return code
    if Dimension.objects.filter(dataset=dataset, code=code).exists():
        return code
    fd = FilterDef.objects.filter(dataset=dataset, code=code).first()
    if fd and fd.dim_code:
        return fd.dim_code
    return code

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

def _iter_vals(dims: dict, key: str):
    v = (dims or {}).get(key)
    if v is None:
        return []
    if isinstance(v, (list, tuple, set)):
        return [x for x in v if x is not None]
    return [v]

def _key_value(dims: dict, key: str):
    v = (dims or {}).get(key)
    if isinstance(v, (list, tuple, set)):
        return "|".join(str(x) for x in v)
    return v

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
    dim_code = _resolve_dim_alias(dataset, dim_code)
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
    if v is None:
        return ""
    if isinstance(v, (list, tuple, set)):
        return ",".join(str(x) for x in v)
    return str(v)

# --------- parsing coordonnée "lat lon [alt]" ou "lon lat [alt]" ----------
_FLOAT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")

def _parse_coords_text(text: str, order: str = "latlon"):
    if not text:
        return (None, None)
    s = str(text).strip()
    nums = _FLOAT_RE.findall(s)
    if len(nums) < 2:
        return (None, None)
    try:
        a = float(nums[0]); b = float(nums[1])
    except Exception:
        return (None, None)
    if (order or "latlon").lower() == "lonlat":
        lon, lat = a, b
    else:
        lon, lat = b, a
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return (None, None)
    return (lon, lat)

# ----------------------------------------------------------------------
# Plan de filtres générique
# ----------------------------------------------------------------------
def _compile_filter_plan(dataset, filters: dict):
    fdefs = {f.code: f for f in FilterDef.objects.filter(dataset=dataset)}
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

    def _add_test(dim_code, op, values):
        vals = _normalize_values(values)
        if not vals:
            return
        op = (op or "in").lower()

        if op in ("in",):
            wanted = set(map(str, vals))
            def _t_in(dims, k=dim_code, wanted=wanted):
                cand = [str(x) for x in _iter_vals(dims, k)]
                return any(c in wanted for c in cand) if cand else False
            tests.append(_t_in)

        elif op == "contains":
            needles = [s.lower() for s in vals]
            def _t_contains(dims, k=dim_code, needles=needles):
                cand = [str(x).lower() for x in _iter_vals(dims, k)]
                return any(any(n in c for n in needles) for c in cand) if cand else False
            tests.append(_t_contains)

        elif op == "between":
            a = vals[0] if vals else None
            b = vals[1] if len(vals) > 1 else None
            def _t_between(dims, k=dim_code, A=a, B=b):
                cand = _iter_vals(dims, k)
                if not cand: return False
                for v in cand:
                    vv = _coerce(v)[1]
                    if A is not None and vv < _coerce(A)[1]: continue
                    if B is not None and vv > _coerce(B)[1]: continue
                    return True
                return False
            tests.append(_t_between)

        elif op == "gte":
            a = vals[0]
            def _t_gte(dims, k=dim_code, A=a):
                cand = _iter_vals(dims, k)
                return any(_coerce(v)[1] >= _coerce(A)[1] for v in cand) if cand else False
            tests.append(_t_gte)

        elif op == "lte":
            b = vals[0]
            def _t_lte(dims, k=dim_code, B=b):
                cand = _iter_vals(dims, k)
                return any(_coerce(v)[1] <= _coerce(B)[1] for v in cand) if cand else False
            tests.append(_t_lte)

        else:
            return _add_test(dim_code, "in", vals)

    for code, values in (filters or {}).items():
        if "__" in code:
            dim_code, op = code.split("__", 1)
        else:
            dim_code, op = code, (fdefs.get(code).op if code in fdefs else "in")
        if code in fdefs and fdefs[code].dim_code:
            dim_code = fdefs[code].dim_code
        _add_test(dim_code, op, values)

    return tests

def _row_passes(tests, dims):
    for t in tests:
        if not t(dims):
            return False
    return True

# ----------------------------------------------------------------------
# Détection repeats
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
    for k in (filters or {}).keys():
        base = k.split("__", 1)[0]
        used_dim_codes.add(base)

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
    for m in (metrics or []):
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
# Query base & strict
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
    cache_key = f"query_{view.id}_{hash(str([group_dims, metrics, filters]))}"
    cached = cache.get(cache_key)
    if cached:
        return cached

    ds = view.dataset
    usage = _collect_usage(ds, group_dims, metrics, filters)

    meas_roots = set()
    for p in (usage["meas_paths"] or {}).values():
        r = _repeat_root(p)
        if r:
            meas_roots.add(r)

    if usage["repeat_roots"]:
        if meas_roots:
            root = next(iter(meas_roots))
        else:
            root = next(iter(usage["repeat_roots"]))
    else:
        result = _run_query_base(view, group_dims, metrics, filters, limit, max_scan)
        cache.set(cache_key, result, 300)
        return result

    tests = _compile_filter_plan(ds, filters or {})
    gdim = list(group_dims or [])
    mlist = list(metrics or [])

    meas_paths = usage["meas_paths"]
    per_item_metric = {
        m.get("code"): (meas_paths.get(m.get("code"), "") or "").startswith(root + "/")
        for m in mlist
    }

    rows_wide = WideRow.objects.filter(dataset=ds)\
        .values_list("dims", "meas", "source_id", "instance_id")[:max_scan].iterator()

    agg_state = defaultdict(lambda: {
        "_dims": None,
        **{m['code']: {"sum": 0.0, "count": 0, "min": None, "max": None} for m in metrics}
    })
    added_static = set()

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
        items = None
        if isinstance(payload, dict):
            items = payload.get(root)

        if not isinstance(items, list):
            dims_aug = dict(dims) if isinstance(dims, dict) else {}
            if isinstance(payload, dict):
                for dcode, dpath in (usage["dim_paths"] or {}).items():
                    if not dpath:
                        continue
                    val = _get_path(payload, dpath)
                    if val is not None:
                        dims_aug[dcode] = val

            if tests and not _row_passes(tests, dims_aug):
                continue

            bkey_vals = [_key_value(dims_aug, d) for d in gdim] if gdim else ["__ALL__"]
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

        for it in items:
            dims_item = dict(dims)
            for dcode, dpath in (usage["dim_paths"] or {}).items():
                if not dpath:
                    continue
                if dpath.startswith(root + "/"):
                    dims_item[dcode] = _get_path(it, dpath)
                else:
                    if dcode not in dims_item and isinstance(payload, dict):
                        v = _get_path(payload, dpath)
                        if v is not None:
                            dims_item[dcode] = v

            if tests and not _row_passes(tests, dims_item):
                continue

            bkey_vals = []
            for d in gdim:
                dpath = (usage["dim_paths"] or {}).get(d, "")
                if dpath.startswith(root + "/"):
                    bkey_vals.append(dims_item.get(d))
                else:
                    bkey_vals.append(dims.get(d) if d in dims else dims_item.get(d))
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
                    raw = _get_path(it, (usage["meas_paths"] or {}).get(code))
                    val = _to_float(raw)
                    if val is None: continue
                    slot["sum"] += val; slot["count"] += 1
                    if slot["min"] is None or val < slot["min"]:
                        slot["min"] = val
                    if slot["max"] is None or val > slot["max"]:
                        slot["max"] = val
                else:
                    marker = (src_id, inst_id, bkey, code)
                    if marker in added_static:
                        continue
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
# Cascade (options)
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
                if not payload:
                    if tests and not _row_passes(tests, dims):
                        continue
                    v = (dims or {}).get(dim_code)
                else:
                    dims_aug = dict(dims) if isinstance(dims, dict) else {}
                    for p_code, _vals in (prefix_filters or {}).items():
                        p_dim = Dimension.objects.filter(dataset=dataset, code=p_code).first()
                        if p_dim and p_dim.path and p_dim.path.startswith(root + "/"):
                            val_p = _get_path(payload, p_dim.path)
                            if val_p is not None:
                                dims_aug[p_code] = val_p
                    if tests and not _row_passes(tests, dims_aug):
                        continue
                    v = _get_path(payload, dpath) if dpath else None
                    if v is None:
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
# Parsing filtres visibles
# ----------------------------------------------------------------------
def _parse_filters(request, view: DatasetView):
    dataset = view.dataset
    dim_codes = set(Dimension.objects.filter(dataset=dataset).values_list("code", flat=True))
    fdef_map = {f.code: f for f in FilterDef.objects.filter(dataset=dataset)}
    allowed_ops = {"in", "contains", "gte", "lte", "between"}

    raw = {}
    for key, vals in request.GET.lists():
        if not vals:
            continue
        flat = []
        for v in vals:
            if v is None:
                continue
            flat.extend([s.strip() for s in str(v).split(",") if s.strip()])
        if not flat:
            continue
        raw[str(key).strip()] = flat

    eff = {}

    def _push(canon_key: str, values: list[str]):
        base = canon_key.split("__", 1)[0]
        cv = _canonize_values_from_data(dataset, base, values)
        if not cv:
            return
        if canon_key in eff:
            seen = set(eff[canon_key])
            for x in cv:
                if x not in seen:
                    eff[canon_key].append(x)
        else:
            eff[canon_key] = cv

    for key, vals in list(raw.items()):
        if "__" not in key:
            continue
        base, op = key.split("__", 1)
        op = op.lower()
        if op not in allowed_ops:
            continue

        if base in dim_codes:
            canon = base
        elif base in fdef_map and fdef_map[base].dim_code:
            canon = fdef_map[base].dim_code
        else:
            continue
        _push(f"{canon}__{op}", vals)

    for key, vals in list(raw.items()):
        if "__" in key:
            continue
        if key in dim_codes:
            canon = key
        elif key in fdef_map and fdef_map[key].dim_code:
            canon = fdef_map[key].dim_code
        else:
            continue
        _push(canon, vals)

    date_dim = request.GET.get("date_dim") or _pick_date_dim(dataset)
    date_from = _parse_date_guess(request.GET.get("from") or request.GET.get("du"))
    date_to   = _parse_date_guess(request.GET.get("to")   or request.GET.get("au"))
    if date_dim:
        date_dim = _resolve_dim_alias(dataset, date_dim)
        if date_from:
            eff[f"{date_dim}__gte"] = [date_from]
        if date_to:
            eff[f"{date_dim}__lte"] = [date_to]

    return eff

# ----------------------------------------------------------------------
# Vue principale
# ----------------------------------------------------------------------
def view_detail(request, slug):
    view = get_object_or_404(
        DatasetView.objects.prefetch_related(
            Prefetch('widgets', queryset=WidgetDef.objects.filter(enabled=True).order_by('order_idx')),
            'exports'
        ),
        slug=slug
    )
    filters = _parse_filters(request, view)

    visible_filters = [f for f in (view.visible_filters or [])]

    def _active_for(alias_code):
        canon = _resolve_dim_alias(view.dataset, alias_code)
        out = []
        for k, vals in (filters or {}).items():
            base = k.split("__", 1)[0]
            if _resolve_dim_alias(view.dataset, base) == canon:
                out.extend(vals)
        return out

    filter_blocks, prefix_alias = [], {}
    for code in visible_filters:
        canon_code = _resolve_dim_alias(view.dataset, code)
        prefix_resolved = { _resolve_dim_alias(view.dataset, k): v for k, v in prefix_alias.items() }
        options = _distinct_values_for_dim_by_prefix(view.dataset, canon_code, prefix_resolved)
        active = _active_for(code)
        filter_blocks.append({"code": code, "options": options, "active": active})
        if active:
            prefix_alias[code] = active

    base_metrics, comp_defs, var_agg_map = prepare_query_metrics(view, include_view_defaults=True)
    headers_raw, rows_raw = run_query_strict(
        view=view,
        group_dims=view.default_group_dims,
        metrics=base_metrics,
        filters=filters,
        limit=100000,
    )
    headers, rows = append_computed_to_rows(headers_raw, rows_raw, comp_defs, var_agg_map, filters=filters)

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
    if only_param:
        match_only = _compile_matcher(only_patterns)
        keep_idx = [i for i, h in enumerate(headers) if match_only(h)]
    elif hide_param:
        match_hide = _compile_matcher(hide_patterns)
        keep_idx = [i for i, h in enumerate(headers) if not match_hide(h)]

    if keep_idx and len(keep_idx) < len(headers):
        headers = [headers[i] for i in keep_idx]
        rows = [[r[i] for i in keep_idx] for r in rows]

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
    widgets_graph = list(view.widgets.filter(enabled=True, type__in=["line", "bar", "pie", "map"]).order_by("order_idx"))

    # ---------- Table widgets ----------
    table_widgets = list(view.widgets.filter(enabled=True, type="table").order_by("order_idx"))
    tables = []
    if not table_widgets:
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

            group_dims = cfg.get("group_dims") or _parse_group_dims_text(_as_csv_text(cfg.get("group_dims_text")))
            metrics_req = cfg.get("metrics") or _parse_metrics_text(_as_csv_text(cfg.get("metrics_text")))
            per_table  = int(cfg.get("per") or 25)

            needed_vars = {}
            for m in metrics_req:
                code = (m.get("code") or "").strip()
                if not code:
                    continue
                cdef = next((c for c in comp_defs if c.get("kind") == "measure" and c.get("code") == code), None)
                if cdef:
                    for v in extract_vars(cdef.get("expr") or "", computed_codes=set(d.get("code") for d in comp_defs)):
                        needed_vars[v] = var_agg_map.get(v, "sum")

            effective_metrics = list(metrics_req) + [{"code": v, "agg": a} for v, a in needed_vars.items()]
            seen_ma = set(); dedup = []
            for m in effective_metrics:
                key = ((m.get("code") or "").strip(), (m.get("agg") or "sum").lower())
                if key in seen_ma:
                    continue
                seen_ma.add(key)
                dedup.append({"code": key[0], "agg": key[1]})
            effective_metrics = dedup

            t_headers_raw, t_rows_raw = run_query_strict(
                view=view,
                group_dims=group_dims,
                metrics=effective_metrics,
                filters=filters,
                limit=100000,
            )

            t_headers, t_rows = append_computed_to_rows(
                t_headers_raw, t_rows_raw, comp_defs, var_agg_map, filters=filters
            )

            wanted_headers = set(group_dims or [])
            for m in metrics_req:
                c = (m.get("code") or "").strip()
                a = (m.get("agg") or "sum").lower()
                if not c:
                    continue
                phys = f"{c}__{a}"
                if phys in t_headers:
                    wanted_headers.add(phys)
                else:
                    wanted_headers.add(c)

            keep_idx_local = [i for i, h in enumerate(t_headers) if h in wanted_headers]
            if keep_idx_local and len(keep_idx_local) < len(t_headers):
                t_headers = [t_headers[i] for i in keep_idx_local]
                t_rows = [[r[i] for i in keep_idx_local] for r in t_rows]

            only_p = _as_csv_text(cfg.get("only_cols")).strip()
            hide_p = _as_csv_text(cfg.get("hide_cols")).strip()

            if only_p or hide_p:
                def _compile_matcher_local(patterns_text: str):
                    if not patterns_text:
                        return lambda h: False
                    testers = []
                    for p in [s.strip() for s in patterns_text.split(",") if s.strip()]:
                        # bugfix: vérifier la présence d'un caractère spécial dans p
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
            "headers": headers,
            "rows": page_obj.object_list,
            "page_obj": page_obj,
            "per": per,
            "per_choices": per_choices,
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
# Endpoint JSON (cascade)
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

    canon_dim = _resolve_dim_alias(view.dataset, dim_code)
    prefix_resolved = { _resolve_dim_alias(view.dataset, k): v for k, v in prefix.items() }

    options = _distinct_values_for_dim_by_prefix(view.dataset, canon_dim, prefix_resolved)
    return JsonResponse({"code": dim_code, "options": options})

# ----------------------------------------------------------------------
# Widgets PNG + JSON MAP
# ----------------------------------------------------------------------
def widget_png(request, slug, widget_id: int):
    view = get_object_or_404(DatasetView, slug=slug)
    try:
        w = WidgetDef.objects.get(pk=widget_id, view=view)
    except WidgetDef.DoesNotExist:
        raise Http404("Widget introuvable")

    cfg = w.config or {}
    filters = _parse_filters(request, view)

    # --------- JSON pour la MAP ---------
    want_json = (request.GET.get("fmt") or request.GET.get("format") or "").lower() == "json"
    if w.type == "map" and want_json:
        metric = cfg.get("metric")
        agg = (cfg.get("agg") or "sum").lower()
        lat_dim = cfg.get("lat_dim")
        lon_dim = cfg.get("lon_dim")
        x_dim = cfg.get("x")  # Dimension X = catégorie (ex. maladie)
        centroids = cfg.get("centroids")
        coords_dim = cfg.get("coords_dim")
        coords_order = (cfg.get("coords_order") or "latlon").lower()

        pts = []

        # 1) lat/lon explicites
        if lat_dim and lon_dim:
            group_dims = [lon_dim, lat_dim] + ([x_dim] if x_dim else [])
            headers, rows = run_query_strict(
                view=view,
                group_dims=group_dims,
                metrics=[{"code": metric, "agg": agg}],
                filters=filters,
                limit=200000,
            )
            if rows:
                ix_lon = headers.index(lon_dim)
                ix_lat = headers.index(lat_dim)
                iy = headers.index(f"{metric}__{agg}")
                ix_cat = headers.index(x_dim) if (x_dim and x_dim in headers) else None
                for r in rows:
                    lon = _to_float(r[ix_lon]); lat = _to_float(r[ix_lat]); val = _to_float(r[iy]) or 0.0
                    if lon is None or lat is None: continue
                    cat = (r[ix_cat] if ix_cat is not None else None)
                    pts.append((lon, lat, val, f"{lon},{lat}", cat))

        # 2) coordonnées texte
        elif coords_dim:
            group_dims = [coords_dim] + ([x_dim] if x_dim else [])
            headers, rows = run_query_strict(
                view=view,
                group_dims=group_dims,
                metrics=[{"code": metric, "agg": agg}],
                filters=filters,
                limit=200000,
            )
            if rows:
                ix_c = headers.index(coords_dim)
                iy = headers.index(f"{metric}__{agg}")
                ix_cat = headers.index(x_dim) if (x_dim and x_dim in headers) else None
                for r in rows:
                    txt = r[ix_c]
                    lon, lat = _parse_coords_text(txt, order=coords_order)
                    if lon is None or lat is None: continue
                    val = _to_float(r[iy]) or 0.0
                    cat = (r[ix_cat] if ix_cat is not None else None)
                    pts.append((lon, lat, val, str(txt), cat))

        # 3) centroids dict + X
        elif isinstance(centroids, dict) and x_dim:
            headers, rows = run_query_strict(
                view=view,
                group_dims=[x_dim],
                metrics=[{"code": metric, "agg": agg}],
                filters=filters,
                limit=100000,
            )
            if rows:
                ix = headers.index(x_dim); iy = headers.index(f"{metric}__{agg}")
                for r in rows:
                    cat = str(r[ix]); val = _to_float(r[iy]) or 0.0
                    pos = centroids.get(cat)
                    if not (isinstance(pos, (list, tuple)) and len(pos) == 2): continue
                    lon = _to_float(pos[0]); lat = _to_float(pos[1])
                    if lon is None or lat is None: continue
                    pts.append((lon, lat, val, cat, cat))

        if not pts:
            return JsonResponse({"points": [], "bounds": None})

        # ---- Catégories globales pour la légende (pondérées par la mesure)
        cats_list = []
        if x_dim:
            hcat, rcat = run_query_strict(
                view=view,
                group_dims=[x_dim],
                metrics=[{"code": metric, "agg": agg}],
                filters=filters,
                limit=200000,
            )
            if rcat:
                ix = hcat.index(x_dim)
                iy = hcat.index(f"{metric}__{agg}")
                for rr in rcat:
                    name = str(rr[ix]) if rr[ix] is not None else ""
                    val = _to_float(rr[iy]) or 0.0
                    if name:
                        cats_list.append({"name": name, "weight": val})

        min_lon = min(p[0] for p in pts); max_lon = max(p[0] for p in pts)
        min_lat = min(p[1] for p in pts); max_lat = max(p[1] for p in pts)

        # Ajout explicite de "cat" dans chaque point + "cats" agrégées
        data = {
            "points": [{"lon": p[0], "lat": p[1], "val": p[2], "label": p[3], "cat": (p[4] if len(p) > 4 else None)} for p in pts],
            "bounds": [min_lat, min_lon, max_lat, max_lon],
            "title": cfg.get("title") or f"Carte: {metric}",
            "cats": cats_list,
        }
        return JsonResponse(data)

    # ---------- Rendu PNG (fallback/graph) ----------
    fig = plt.figure()
    ax = fig.gca()

    def _to_png(fig):
        buf = BytesIO()
        try:
            fig.tight_layout()
        except Exception:
            pass
        fig.savefig(buf, format="png")
        plt.close(fig)
        buf.seek(0)
        return HttpResponse(buf.getvalue(), content_type="image/png")

    def _clean_xy(xs, ys):
        clean_x, clean_y = [], []
        for a, b in zip(xs or [], ys or []):
            if a is None or b is None:
                continue
            try:
                _ = float(b)
            except Exception:
                continue
            clean_x.append(a)
            clean_y.append(b)
        return clean_x, clean_y

    if w.type == "kpi":
        metric = (cfg.get("metric") or "").strip()
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

    if w.type not in ("line", "bar", "pie", "map"):
        ax.axis("off")
        plt.text(0.5, 0.5, f"Type non supporté: {w.type}", ha="center", va="center")
        return _to_png(fig)

    x = cfg.get("x")
    metric = cfg.get("metric")
    agg = (cfg.get("agg") or "sum").lower()

    if w.type != "map" and (not x or not metric):
        ax.axis("off")
        plt.text(0.5, 0.5, "Configuration incomplète", ha="center", va="center")
        return _to_png(fig)

    base_metrics, comp_defs, var_agg_map = prepare_query_metrics(view, include_view_defaults=False)

    def _get_comp(code, kind=None):
        for c in comp_defs:
            if c["code"] == code and (kind is None or c.get("kind") == kind):
                return c
        return None

    comp_x = _get_comp(x, kind="dimension") if x else None
    comp_y = _get_comp(metric, kind="measure") if metric else None

    def _format_label(v):
        try:
            f = float(v)
            if abs(f - round(f)) < 1e-6:
                return str(int(round(f)))
            return f"{f:.2f}"
        except Exception:
            return str(v)

    def _apply_line_style(xs, ys, title_text):
        xs, ys = _clean_xy(xs, ys)
        ax.get_yaxis().set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.grid(False)
        ax.plot(xs, ys)
        for xi, yi in zip(xs, ys):
            ax.annotate(_format_label(yi), xy=(xi, yi), xytext=(0, 5),
                        textcoords="offset points", ha="center", va="bottom", fontsize=9)
        ax.set_xlabel(x)
        ax.set_title(title_text)
        fig.autofmt_xdate()

    def _apply_bar_style(xs, ys, title_text):
        xs, ys = _clean_xy(xs, ys)
        cycle = plt.rcParams['axes.prop_cycle'].by_key().get('color', ['C0'])
        colors = [cycle[i % len(cycle)] for i in range(len(xs))]
        bars = ax.bar([str(v) for v in xs], ys, color=colors)
        ax.get_yaxis().set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.grid(False)
        for b, val in zip(bars, ys):
            ax.annotate(_format_label(val),
                        xy=(b.get_x() + b.get_width() / 2, b.get_height()),
                        xytext=(0, 3), textcoords="offset points",
                        ha="center", va="bottom", fontsize=9)
        ax.set_xlabel(x)
        ax.set_title(title_text)
        fig.autofmt_xdate()

    def _apply_pie(xs, ys, title_text):
        total = sum(ys) if ys else 0
        if total == 0:
            ax.axis("off")
            plt.text(0.5, 0.5, "Aucune donnée", ha="center", va="center")
            return
        ax.pie(ys, labels=[str(v) for v in xs],
               autopct=lambda p: f"{p:.1f}%" if p > 0 else "")
        ax.set_title(title_text)

    # X calculée
    if w.type in ("line", "bar", "pie") and comp_x:
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
        title_text = cfg.get("title") or f"{metric} par {x}"

        if w.type == "line":
            _apply_line_style(xs, ys, title_text)
        elif w.type == "bar":
            _apply_bar_style(xs, ys, title_text)
        else:
            _apply_pie(xs, ys, cfg.get("title") or f"Répartition de {metric} par {x}")
        return _to_png(fig)

    # X normale & Y calculée
    if w.type in ("line", "bar", "pie") and comp_y:
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

        xs, ys = _clean_xy(xs, ys)
        if not xs:
            ax.axis("off"); plt.text(0.5, 0.5, "Aucune donnée", ha="center", va="center"); return _to_png(fig)

        title_text = cfg.get("title") or f"{metric} par {x}"
        if w.type == "line":
            _apply_line_style(xs, ys, title_text)
        elif w.type == "bar":
            _apply_bar_style(xs, ys, title_text)
        else:
            _apply_pie(xs, ys, cfg.get("title") or f"Répartition de {metric} par {x}")
        return _to_png(fig)

    # MAP (PNG fallback)
    if w.type == "map":
        title_text = cfg.get("title") or f"Carte"
        ax.axis("off")
        plt.text(0.5, 0.5, "Utiliser l'affichage carte interactif du template.", ha="center", va="center")
        ax.set_title(title_text)
        return _to_png(fig)

    # X & Y non calculés
    if w.type in ("line", "bar", "pie"):
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
        xs, ys = _clean_xy(xs, ys)
        if not xs:
            ax.axis("off"); plt.text(0.5, 0.5, "Aucune donnée", ha="center", va="center"); return _to_png(fig)

        title_text = cfg.get("title") or f"{metric} par {x}"
        if w.type == "line":
            _apply_line_style(xs, ys, title_text)
        elif w.type == "bar":
            _apply_bar_style(xs, ys, title_text)
        else:
            _apply_pie(xs, ys, cfg.get("title") or f"Répartition de {metric} par {x}")
        return _to_png(fig)

    ax.axis("off")
    plt.text(0.5, 0.5, "Type non supporté", ha="center", va="center")
    return _to_png(fig)

# ----------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------
def export_view(request, slug, export_id):
    exp = get_object_or_404(ExportDef, pk=export_id, view__slug=slug)
    view = exp.view
    cfg = exp.config or {}

    eff_filters = _parse_filters(request, view)

    base_metrics, comp_defs, var_agg_map = prepare_query_metrics(view, include_view_defaults=False)

    metrics_req = cfg.get("metrics", view.default_metrics)
    if isinstance(metrics_req, str):
        metrics_req = _parse_metrics_text(metrics_req)

    needed_vars = {}
    for m in metrics_req:
        code = (m.get("code") or "").strip()
        if not code:
            continue
        cdef = next((c for c in comp_defs if c.get("kind") == "measure" and c.get("code") == code), None)
        if cdef:
            for v in extract_vars(cdef.get("expr") or "", computed_codes=set(d.get("code") for d in comp_defs)):
                needed_vars[v] = var_agg_map.get(v, "sum")

    effective_metrics = list(metrics_req) + [{"code": v, "agg": a} for v, a in needed_vars.items()]
    seen = set(); dedup = []
    for m in effective_metrics:
        key = ((m.get("code") or "").strip(), (m.get("agg") or "sum").lower())
        if key in seen:
            continue
        seen.add(key); dedup.append({"code": key[0], "agg": key[1]})
    effective_metrics = dedup

    headers_raw, rows_raw = run_query_strict(
        view=view,
        group_dims=cfg.get("group_dims", view.default_group_dims),
        metrics=effective_metrics,
        filters=eff_filters,
        limit=500000,
    )

    headers, rows = append_computed_to_rows(headers_raw, rows_raw, comp_defs, var_agg_map, filters=eff_filters)

    wanted = set(cfg.get("group_dims", view.default_group_dims) or [])
    for m in metrics_req:
        c = (m.get("code") or "").strip()
        a = (m.get("agg") or "sum").lower()
        if not c:
            continue
        if any(cd.get("kind") == "measure" and cd.get("code") == c for cd in comp_defs):
            wanted.add(c)
        else:
            wanted.add(f"{c}__{a}")

    keep_idx = [i for i, h in enumerate(headers) if h in wanted]
    if keep_idx and len(keep_idx) < len(headers):
        headers = [headers[i] for i in keep_idx]
        rows = [[r[i] for i in keep_idx] for r in rows]

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
        resp["Content-Disposition"] = f'attachment; filename="{filename}.xlsx'
        return resp

    return HttpResponse("Format non supporté", status=400)
