# semantic_layer/querybuilder.py
from django.db import connection
import re

def safe_ident(s: str) -> str:
    """
    Transforme n'importe quelle chaîne en identifiant SQL sûr (alias).
    - remplace tout sauf [A-Za-z0-9_] par '_'
    - préfixe si ça commence par un chiffre
    - tronque à 63 caractères (limite PostgreSQL)
    """
    s = s or ""
    s = re.sub(r"[^A-Za-z0-9_]", "_", s)
    if not s or s[0].isdigit():
        s = f"c_{s}"
    return s[:63]

def build_and_run_query(dataset, group_dims: list, metrics: list, filters: dict, limit: int = 5000):
    """
    dataset: DatasetLogical
    group_dims: ex ["date","region","maladie"] (codes de Dimension, PAS les paths Kobo)
    metrics: list[dict] ex [{"code":"nb_malades","agg":"sum"},{"code":"nb_morts","agg":"sum"}]
    filters: dict ex {"periode": ["2025-01-01","2025-12-31"], "region":["ML-1","ML-2"], "maladie":["PPR"]}
    Retourne (headers, rows)
    """
    table = "semantic_layer_widerow"  # table du modèle WideRow

    # Colonnes dynamiques → dims->>code , meas->>code::numeric
    select_cols = []
    group_by_cols = []

    # Dimensions (GROUP BY)
    for d in group_dims or []:
        col_expr = f"(w.dims->>'{d}')"
        alias = safe_ident(d)
        select_cols.append(f"{col_expr} AS \"{alias}\"")
        group_by_cols.append(col_expr)

    # Métriques (agrégations)
    for m in metrics or []:
        code = m.get("code")
        agg = (m.get("agg") or "sum").lower()
        if not code:
            continue
        if agg == "count":
            alias = safe_ident(f"{code}__count")
            select_cols.append(f"COUNT(*) AS \"{alias}\"")
        else:
            # Agrégats autorisés
            if agg not in {"sum", "avg", "min", "max"}:
                agg = "sum"
            alias = safe_ident(f"{code}__{agg}")
            select_cols.append(f"{agg}((w.meas->>'{code}')::numeric) AS \"{alias}\"")

    # Si aucune dimension/metric fournie → COUNT(*)
    if not select_cols:
        select_cols = ["COUNT(*) AS \"n\""]

    where_clauses = ["w.dataset_id = %s"]
    params = [dataset.id]

    # Filtres dynamiques (FilterDef définit dim/op)
    # filters = {filter_code: value}, où value peut être:
    #  - list/tuple pour 'in'
    #  - [start, end] pour 'between'
    #  - str pour 'eq' / 'contains' / 'gte' / 'lte'
    for fdef in dataset.filters.all():
        v = filters.get(fdef.code)
        if v is None:
            continue
        col = f"(w.dims->>'{fdef.dim_code}')"
        op = (fdef.op or "in").lower()

        if op == "in":
            if not isinstance(v, (list, tuple)):
                v = [v]
            where_clauses.append(f"{col} = ANY(%s)")
            params.append(list(v))

        elif op == "eq":
            where_clauses.append(f"{col} = %s")
            params.append(v)

        elif op == "contains":
            where_clauses.append(f"{col} ILIKE %s")
            params.append(f"%{v}%")

        elif op == "between":
            # Typiquement pour dates 'YYYY-MM-DD'
            if isinstance(v, (list, tuple)) and len(v) == 2:
                start, end = v[0], v[1]
                if start is not None:
                    where_clauses.append(f"{col} >= %s")
                    params.append(start)
                if end is not None:
                    where_clauses.append(f"{col} <= %s")
                    params.append(end)

        elif op == "gte":
            where_clauses.append(f"{col} >= %s")
            params.append(v)

        elif op == "lte":
            where_clauses.append(f"{col} <= %s")
            params.append(v)

        else:
            # Par défaut, on traite comme eq
            where_clauses.append(f"{col} = %s")
            params.append(v)

    select_sql = ", ".join(select_cols)
    group_sql = f" GROUP BY {', '.join(group_by_cols)}" if group_by_cols else ""
    where_sql = " AND ".join(where_clauses)

    sql = f"""
        SELECT {select_sql}
        FROM {table} w
        WHERE {where_sql}
        {group_sql}
        LIMIT {int(limit)}
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
        headers = [c[0] for c in cur.description]

    return headers, rows
