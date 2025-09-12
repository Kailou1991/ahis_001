from django.db import models
from django.core.exceptions import ValidationError, NON_FIELD_ERRORS


class DatasetView(models.Model):
    """
    Vue logique déclarée par l'admin sur un DatasetLogical :
    - choisit les dimensions de regroupement par défaut
    - prescrit des métriques par défaut avec agrégations
    - expose les filtres visibles
    - (optionnel) MV pour booster les perfs
    """
    dataset = models.ForeignKey(
        "semantic_layer.DatasetLogical",
        on_delete=models.CASCADE,
        related_name="views",
    )
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)

    # ex: ["date","region","maladie"]
    default_group_dims = models.JSONField(default=list, blank=True)
    # ex: [{"code":"nb_malades","agg":"sum"}]
    default_metrics = models.JSONField(default=list, blank=True)
    # ex: ["region","maladie"]
    visible_filters = models.JSONField(default=list, blank=True)

    # Options d'affichage table
    # ex: ["province","vaccines__sum","*__sum"]
    table_only_cols   = models.JSONField(default=list, blank=True)
    # ex: ["*and__sum", "PPR__sum$", "Peste*__sum$"]
    table_hidden_cols = models.JSONField(default=list, blank=True)

    # Cache / formules calculées (toujours non nul)
    computed_metrics = models.JSONField(
        default=list,
        blank=True,
        help_text="Cache de métriques calculées à partir de la config. Toujours non nul."
    )

    menu_title = models.CharField(max_length=120, default="")
    menu_icon = models.CharField(max_length=50, default="bi-graph-up")

    # Materialized view (optionnel)
    materialized_name = models.CharField(max_length=128, blank=True, null=True)
    materialized_last_refresh = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ("slug",)

    def __str__(self) -> str:
        return self.title or self.slug

    # --- Sécurité : ne jamais persister None dans les JSONField "list-like" ---
    def clean(self):
        super().clean()
        if self.default_group_dims is None:
            self.default_group_dims = []
        if self.default_metrics is None:
            self.default_metrics = []
        if self.visible_filters is None:
            self.visible_filters = []
        if self.table_only_cols is None:
            self.table_only_cols = []
        if self.table_hidden_cols is None:
            self.table_hidden_cols = []
        if self.computed_metrics is None:
            self.computed_metrics = []

    def save(self, *args, **kwargs):
        # Filet de sécurité au cas où save() est appelé sans full_clean()
        if self.default_group_dims is None:
            self.default_group_dims = []
        if self.default_metrics is None:
            self.default_metrics = []
        if self.visible_filters is None:
            self.visible_filters = []
        if self.table_only_cols is None:
            self.table_only_cols = []
        if self.table_hidden_cols is None:
            self.table_hidden_cols = []
        if self.computed_metrics is None:
            self.computed_metrics = []
        super().save(*args, **kwargs)


class WidgetDef(models.Model):
    """
    Définition de widget (kpi_card | line | bar | pie | table | map).
    Les paramètres sont stockés dans `config` (JSON).

    MAP — 3 modes supportés :
      A) lat/lon         -> {"metric":"...", "agg":"sum", "lat_dim":"lat","lon_dim":"lon", ...}
      B) centroids (x)   -> {"metric":"...", "agg":"sum", "x":"region","centroids":{"KAYES":[lon,lat],...}, ...}
      C) coords texte    -> {"metric":"...", "agg":"sum", "coords_dim":"Geoloc", "coords_order":"latlon"|"lonlat", ...}
    """

    TYPE_TABLE = "table"
    TYPE_LINE = "line"
    TYPE_BAR = "bar"
    TYPE_PIE = "pie"
    TYPE_KPI_CARD = "kpi_card"
    TYPE_KPI = "kpi"
    TYPE_MAP = "map"

    TYPE_CHOICES = [
        (TYPE_TABLE, "table"),
        (TYPE_LINE, "line"),
        (TYPE_BAR, "bar"),
        (TYPE_PIE, "pie"),
        (TYPE_KPI_CARD, "kpi_card"),
        (TYPE_KPI, "kpi"),
        (TYPE_MAP, "map"),
    ]

    view = models.ForeignKey(
        DatasetView,
        on_delete=models.CASCADE,
        related_name="widgets",
    )
    order_idx = models.IntegerField(default=0)
    type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    enabled = models.BooleanField(default=True)

    # ex:
    #  KPI  : {"metric":"vaccines","agg":"sum","title":"Total","color":"primary"}
    #  LINE : {"x":"date","metric":"vaccines","agg":"sum","title":"Évolution"}
    #  BAR  : {"x":"province","metric":"vaccines","agg":"sum","title":"Par province"}
    #  PIE  : {"x":"maladie","metric":"vaccines","agg":"sum","title":"Répartition"}
    #  TABLE: {"title":"...", "group_dims":[...], "metrics":[...], "filters":{...}, "per":25}
    #  MAP  : voir docstring ci-dessus (A / B / C)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("order_idx", "id")

    def __str__(self) -> str:
        return f"{self.view.slug} · #{self.order_idx} · {self.type}"

    # ---------- Helpers "ergonomiques" ----------
    def set_map_latlon(self, lat_dim: str, lon_dim: str, title: str = "", show_labels: bool = True, **extra):
        cfg = dict(self.config or {})
        cfg.update({
            "lat_dim": lat_dim,
            "lon_dim": lon_dim,
            "title": title or cfg.get("title") or "Carte",
            "show_labels": bool(show_labels),
        })
        cfg.update(extra or {})
        self.config = cfg

    def set_map_centroids(self, x_dim: str, centroids: dict, title: str = "", show_labels: bool = True, **extra):
        cfg = dict(self.config or {})
        cfg.update({
            "x": x_dim,
            "centroids": centroids,
            "title": title or cfg.get("title") or "Carte",
            "show_labels": bool(show_labels),
        })
        cfg.update(extra or {})
        self.config = cfg

    def set_map_coords(self, coords_dim: str, coords_order: str = "latlon",
                       title: str = "", show_labels: bool = True, **extra):
        """Mode C: champ texte contenant 'lat lon [alt]' ou 'lon lat [alt]'."""
        cfg = dict(self.config or {})
        cfg.update({
            "coords_dim": coords_dim,
            "coords_order": (coords_order or "latlon").lower(),
            "title": title or cfg.get("title") or "Carte",
            "show_labels": bool(show_labels),
        })
        cfg.update(extra or {})
        self.config = cfg

    # ---------- Validation/normalisation ----------
    def _validate_required(self, keys):
        """Valide des clés requises dans config et renvoie une erreur *globale* (NON_FIELD_ERRORS)."""
        missing = [k for k in keys if not (self.config or {}).get(k)]
        if missing:
            raise ValidationError({
                NON_FIELD_ERRORS: [f"Champs requis manquants pour {self.type}: {', '.join(missing)}"]
            })

    def clean(self):
        super().clean()
        if self.config is None:
            self.config = {}

        cfg = dict(self.config or {})

        # Valeur par défaut pour l'agg (sauf table)
        if self.type != self.TYPE_TABLE and "agg" not in cfg:
            cfg["agg"] = cfg.get("agg", "sum")

        # Validation par type
        if self.type in {self.TYPE_LINE, self.TYPE_BAR, self.TYPE_PIE}:
            self._validate_required(["x", "metric", "agg"])
        elif self.type in {self.TYPE_KPI, self.TYPE_KPI_CARD}:
            self._validate_required(["metric", "agg"])
        elif self.type == self.TYPE_TABLE:
            # Normalisation douce
            for k in ("group_dims", "metrics"):
                if k in cfg and cfg[k] is None:
                    cfg[k] = []
        elif self.type == self.TYPE_MAP:
            metric = (cfg.get("metric") or "").strip()
            agg = (cfg.get("agg") or "").strip().lower()

            has_latlon    = bool(cfg.get("lat_dim")) and bool(cfg.get("lon_dim"))
            has_centroids = bool(cfg.get("x")) and isinstance(cfg.get("centroids"), dict)
            has_coords    = bool(cfg.get("coords_dim"))

            if not metric or not agg:
                raise ValidationError({
                    NON_FIELD_ERRORS: ["MAP : fournir 'metric' et 'agg'."]
                })

            if not (has_latlon or has_centroids or has_coords):
                raise ValidationError({
                    NON_FIELD_ERRORS: [
                        "MAP : fournir soit lat_dim + lon_dim, soit x + centroids {code:[lon,lat]}, "
                        "soit coords_dim (champ texte 'lat lon [alt]')."
                    ]
                })

            if has_centroids:
                bad = []
                for k, v in (cfg.get("centroids") or {}).items():
                    if not (isinstance(v, (list, tuple)) and len(v) == 2):
                        bad.append(k); continue
                    try:
                        float(v[0]); float(v[1])
                    except Exception:
                        bad.append(k)
                if bad:
                    raise ValidationError({
                        NON_FIELD_ERRORS: [
                            f"MAP : centroids invalides pour: {', '.join(bad)} (attendu [lon, lat])."
                        ]
                    })

            if has_coords:
                order = (cfg.get("coords_order") or "latlon").lower()
                if order not in {"latlon", "lonlat"}:
                    raise ValidationError({
                        NON_FIELD_ERRORS: ["MAP : 'coords_order' doit être 'latlon' ou 'lonlat'."]
                    })

        self.config = cfg

    def save(self, *args, **kwargs):
        if self.config is None:
            self.config = {}
        super().save(*args, **kwargs)


class ExportDef(models.Model):
    FORMAT_CSV = "csv"
    FORMAT_XLSX = "xlsx"
    FORMAT_CHOICES = [
        (FORMAT_CSV, "csv"),
        (FORMAT_XLSX, "xlsx"),
    ]

    view = models.ForeignKey(
        DatasetView,
        on_delete=models.CASCADE,
        related_name="exports",
    )
    name = models.CharField(max_length=120)
    format = models.CharField(max_length=10, choices=FORMAT_CHOICES)  # csv|xlsx
    # {"group_dims":[...], "metrics":[...], "filters":{...}}
    config = models.JSONField(default=dict, blank=True)
    filename_pattern = models.CharField(
        max_length=200,
        default="AHIS_{slug}_{date}",
    )

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.view.slug} · {self.name} ({self.format})"

    def clean(self):
        super().clean()
        if self.config is None:
            self.config = {}

    def save(self, *args, **kwargs):
        if self.config is None:
            self.config = {}
        super().save(*args, **kwargs)
