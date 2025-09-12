# publishing/mv.py
import re
from django.db import connection, transaction
from django.utils import timezone
from .models import DatasetView
from semantic_layer.querybuilder import build_and_run_query


def _safe_ident(name: str, prefix: str = "c_") -> str:
    """
    Transforme un nom arbitraire en identifiant SQL sûr.
    """
    s = re.sub(r"[^0-9a-zA-Z_]", "_", name or "")
    if not s or s[0].isdigit():
        s = f"{prefix}{s}"
    return s.lower()


def _table_name_for_view(view: DatasetView) -> str:
    """
    Nom de la table matérialisée à partir du slug de la vue.
    """
    return _safe_ident(f"mv_{view.slug}", prefix="mv_")


def create_or_replace_mv_for_view(view: DatasetView) -> str:
    """
    Construit (ou reconstruit) une table matérialisée pour la vue donnée.
    Implémentation portable (Postgres/SQLite) :
      - exécute la requête analytique via build_and_run_query
      - crée une table "mv_<slug>" et y insère les lignes
      - met à jour view.materialized_name / materialized_last_refresh
    """
    # 1) Récupérer les données agrégées de la vue
    headers, rows = build_and_run_query(
        dataset=view.dataset,
        group_dims=view.default_group_dims or [],
        metrics=view.default_metrics or [],
        filters={},            # MV de base sans filtre (global)
        limit=10_000_000,      # généreux ; adapter si besoin
    )
    if not headers:
        raise ValueError("Aucune donnée disponible pour construire la MV.")

    # Heuristique: dimension vs mesure
    metric_codes = {m.get("code") for m in (view.default_metrics or [])}
    vendor = connection.vendor  # 'postgresql' | 'sqlite' | ...

    # 2) Construire le schéma de la table
    col_defs = []
    col_names = []
    metric_idx = []
    for i, h in enumerate(headers):
        cname = _safe_ident(h)
        col_names.append(cname)
        is_metric = (h in metric_codes) or ("__" in h)
        if is_metric:
            metric_idx.append(i)
        if is_metric:
            col_type = "DOUBLE PRECISION" if vendor == "postgresql" else "REAL"
        else:
            col_type = "TEXT"
        col_defs.append(f'"{cname}" {col_type}')

    table = _table_name_for_view(view)

    # 3) Drop + Create + Insert
    with connection.cursor() as cur, transaction.atomic():
        # Drop table si existe
        cur.execute(f'DROP TABLE IF EXISTS "{table}"')
        # Create table
        cur.execute(f'CREATE TABLE "{table}" ({", ".join(col_defs)})')
        # Insert
        placeholders = ", ".join(["%s"] * len(headers))
        cols_sql = ", ".join(f'"{c}"' for c in col_names)
        insert_sql = f'INSERT INTO "{table}" ({cols_sql}) VALUES ({placeholders})'

        def cast_row(r):
            r = list(r)
            for j in metric_idx:
                try:
                    r[j] = float(r[j]) if r[j] is not None else None
                except (ValueError, TypeError):
                    r[j] = None
            return r

        cur.executemany(insert_sql, [cast_row(r) for r in rows])

        # (Optionnel) Ajouter des index sur 1-2 premières dimensions
        if view.default_group_dims:
            for d in view.default_group_dims[:2]:
                idx_col = _safe_ident(d)
                cur.execute(
                    f'CREATE INDEX IF NOT EXISTS "ix_{table}_{idx_col}" '
                    f'ON "{table}" ("{idx_col}")'
                )

    # 4) Marquer la vue comme matérialisée
    view.materialized_name = table
    view.materialized_last_refresh = timezone.now()
    view.save(update_fields=["materialized_name", "materialized_last_refresh"])

    return table


def refresh_mv(materialized_name: str):
    """
    Rafraîchit la MV en retrouvant la vue par son nom matérialisé
    puis en appelant create_or_replace_mv_for_view(view).
    """
    try:
        view = DatasetView.objects.get(materialized_name=materialized_name)
    except DatasetView.DoesNotExist:
        return None
    return create_or_replace_mv_for_view(view)
