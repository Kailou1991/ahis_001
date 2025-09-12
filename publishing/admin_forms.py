from __future__ import annotations

from typing import Optional
from django import forms

from .models import WidgetDef, DatasetView, ExportDef
from semantic_layer.models import Dimension, Measure
from .compute import prepare_query_metrics  # computed depuis la vue


AGG_CHOICES = [
    ("sum", "sum"), ("avg", "avg"), ("min", "min"),
    ("max", "max"), ("count", "count"),
]
COLOR_CHOICES = [
    ("primary", "primary"), ("success", "success"), ("info", "info"),
    ("warning", "warning"), ("danger", "danger"), ("secondary", "secondary"),
]


# ------------------------
# Parseurs simples
# ------------------------
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


# =========================
# WidgetDefForm
# =========================
class WidgetDefForm(forms.ModelForm):
    # Champs “plats” (écrivent/lecture dans config)
    title = forms.CharField(required=False, label="Titre")
    metric = forms.ChoiceField(required=False, label="Mesure")
    x = forms.ChoiceField(required=False, label="Dimension X")
    agg = forms.ChoiceField(required=False, choices=AGG_CHOICES, label="Agrégation")
    color = forms.ChoiceField(required=False, choices=COLOR_CHOICES, label="Couleur (KPI)")

    # --- MAP (stocké dans config) ---
    MAP_MODES = [
        ("latlon", "Lat/Lon (dimensions lat/lon)"),
        ("coords", "Coordonnée texte (\"lat lon [alt]\")"),
        ("centroids", "Centroids (x + dictionnaire)"),
    ]
    map_mode = forms.ChoiceField(required=False, choices=MAP_MODES, label="Mode carte")
    lat_dim = forms.ChoiceField(required=False, label="Latitude (dim)")
    lon_dim = forms.ChoiceField(required=False, label="Longitude (dim)")
    coords_dim = forms.ChoiceField(required=False, label="Champ coordonnées")
    coords_order = forms.ChoiceField(
        required=False, label="Ordre coords",
        choices=[("latlon", "lat lon"), ("lonlat", "lon lat")],
        initial="latlon",
    )
    centroids = forms.JSONField(required=False, label="Centroids (JSON {code:[lon,lat]})")
    show_labels = forms.BooleanField(required=False, initial=True, label="Afficher les étiquettes")

    # --- TABLE helpers (stocké dans config) ---
    group_dims_text = forms.CharField(
        required=False, label="Group dims (table)",
        help_text='Ex: province, departement'
    )
    metrics_text = forms.CharField(
        required=False, label="Metrics (table)",
        help_text='Ex: PPR:sum; PPCB:sum (séparées par ;)'
    )
    per = forms.IntegerField(
        required=False, label="Page size (table)",
        help_text="Par défaut 25 si vide"
    )
    only_cols = forms.CharField(
        required=False, label="Colonnes à garder (table)",
        help_text='Motifs FNMatch/regex. Ex: "province, *__sum"'
    )
    hide_cols = forms.CharField(required=False, label="Colonnes à masquer (table)")

    class Meta:
        model = WidgetDef
        fields = (
            "view", "enabled", "order_idx", "type",
            "title", "metric", "x", "agg", "color",
            # MAP
            "map_mode", "lat_dim", "lon_dim",
            "coords_dim", "coords_order",
            "centroids", "show_labels",
            # TABLE
            "group_dims_text", "metrics_text", "per", "only_cols", "hide_cols",
        )

    # ---- helpers computed
    def _computed_from_view(self, view: DatasetView):
        try:
            _, comp_defs, _ = prepare_query_metrics(view, include_view_defaults=True)
            cm = [c for c in comp_defs if c.get("kind") == "measure"]
            cd = [c for c in comp_defs if c.get("kind") == "dimension"]
            return cm, cd
        except Exception:
            return [], []

    def __init__(self, *args, **kwargs):
        # Contexte éventuellement injecté par l’admin inline/édition
        self.view: Optional[DatasetView] = kwargs.pop("view", None)
        super().__init__(*args, **kwargs)

        # >>> Utiliser le contexte injecté par l'inline si présent
        if self.view is None:
            self.view = getattr(self, "VIEW_CTX", None)

        # 1) Déduire la View courante si non fournie (cas "Ajouter" hors inline)
        if self.view is None:
            vid = None
            # a) POST en cours
            if hasattr(self, "data") and self.data:
                vid = self.data.get("view") or self.data.get("widgetdef-view")
            # b) initial
            if not vid:
                vid = self.initial.get("view")
            # c) instance
            if not vid and getattr(self.instance, "view_id", None):
                vid = self.instance.view_id
            # Résolution DB
            try:
                if vid:
                    self.view = DatasetView.objects.get(pk=int(vid))
            except Exception:
                self.view = None

        # 2) Construire les choices
        metric_choices = [("", "—")]
        x_choices = [("", "—")]
        lat_choices = [("", "—")]
        lon_choices = [("", "—")]
        coords_choices = [("", "—")]

        if self.view:
            # physiques
            for m in Measure.objects.filter(dataset=self.view.dataset).order_by("code"):
                metric_choices.append((m.code, m.label or m.code))
            for d in Dimension.objects.filter(dataset=self.view.dataset).order_by("code"):
                label = d.label or d.code
                x_choices.append((d.code, label))
                lat_choices.append((d.code, label))
                lon_choices.append((d.code, label))
                coords_choices.append((d.code, label))
            # computed
            cm, cd = self._computed_from_view(self.view)
            for c in cm:
                code = c.get("code")
                if code:
                    metric_choices.append((code, f"{c.get('title') or c.get('label') or code} (computed)"))
            for c in cd:
                code = c.get("code")
                if code:
                    x_choices.append((code, f"{c.get('title') or c.get('label') or code} (computed)"))

        # Conserver d’anciens choix
        cfg = self.instance.config or {}
        cur_metric = cfg.get("metric") or ""
        cur_x = cfg.get("x") or ""
        cur_lat = cfg.get("lat_dim") or ""
        cur_lon = cfg.get("lon_dim") or ""
        cur_coords = cfg.get("coords_dim") or ""

        def _keep(choice_list, val):
            if val and all(k != val for k, _ in choice_list):
                choice_list.insert(1, (val, f"{val} (existant)"))

        _keep(metric_choices, cur_metric)
        _keep(x_choices, cur_x)
        _keep(lat_choices, cur_lat)
        _keep(lon_choices, cur_lon)
        _keep(coords_choices, cur_coords)

        self.fields["metric"].choices = metric_choices
        self.fields["x"].choices = x_choices
        self.fields["lat_dim"].choices = lat_choices
        self.fields["lon_dim"].choices = lon_choices
        self.fields["coords_dim"].choices = coords_choices

        # 3) Initialiser depuis config
        self.fields["title"].initial = cfg.get("title", "")
        self.fields["metric"].initial = cur_metric
        self.fields["x"].initial = cur_x
        self.fields["agg"].initial = cfg.get("agg", "sum")
        self.fields["color"].initial = cfg.get("color", "primary")
        self.fields["map_mode"].initial = cfg.get("map_mode", "latlon")
        self.fields["lat_dim"].initial = cur_lat
        self.fields["lon_dim"].initial = cur_lon
        self.fields["coords_dim"].initial = cur_coords
        self.fields["coords_order"].initial = cfg.get("coords_order", "latlon")
        self.fields["centroids"].initial = cfg.get("centroids", {})
        self.fields["show_labels"].initial = cfg.get("show_labels", True)

        # TABLE helpers
        self.fields["group_dims_text"].initial = cfg.get(
            "group_dims_text", ", ".join(cfg.get("group_dims", []) or [])
        )
        if "metrics_text" in cfg:
            metrics_text = cfg["metrics_text"]
        else:
            parts = []
            for m in (cfg.get("metrics") or []):
                parts.append(f"{(m.get('code') or '').strip()}:{(m.get('agg') or 'sum').strip().lower()}")
            metrics_text = "; ".join([p for p in parts if p and not p.endswith(":")])
        self.fields["metrics_text"].initial = metrics_text
        self.fields["per"].initial = cfg.get("per", None)
        self.fields["only_cols"].initial = cfg.get("only_cols", "")
        self.fields["hide_cols"].initial = cfg.get("hide_cols", "")

    # Autoriser valeurs libres
    def clean_metric(self):
        v = self.cleaned_data.get("metric")
        return "" if v is None else v

    def clean_x(self):
        v = self.cleaned_data.get("x")
        return "" if v is None else v

    # >>> Important: pré-hydrater config pour le model.clean()
    def clean(self):
        cleaned = super().clean()
        cfg = dict(getattr(self.instance, "config", {}) or {})

        # Champs requis par le model.clean()
        cfg["metric"] = (self.cleaned_data.get("metric") or "").strip()
        cfg["agg"] = (self.cleaned_data.get("agg") or "sum").strip().lower()
        # AJOUT: x doit être présent pour line/bar/pie (et utilisé par le mode centroids)
        cfg["x"] = (self.cleaned_data.get("x") or "").strip()

        mm = (self.cleaned_data.get("map_mode") or "latlon").strip()
        cfg["map_mode"] = mm
        cfg["show_labels"] = bool(self.cleaned_data.get("show_labels"))

        if mm == "latlon":
            cfg["lat_dim"] = (self.cleaned_data.get("lat_dim") or "").strip()
            cfg["lon_dim"] = (self.cleaned_data.get("lon_dim") or "").strip()
            cfg.pop("coords_dim", None)
            cfg.pop("coords_order", None)
            cfg.pop("centroids", None)
        elif mm == "coords":
            cfg["coords_dim"] = (self.cleaned_data.get("coords_dim") or "").strip()
            cfg["coords_order"] = (self.cleaned_data.get("coords_order") or "latlon").strip().lower()
            cfg.pop("lat_dim", None)
            cfg.pop("lon_dim", None)
            cfg.pop("centroids", None)
        elif mm == "centroids":
            # cfg["x"] déjà posé ci-dessus
            cfg["centroids"] = self.cleaned_data.get("centroids") or {}
            cfg.pop("lat_dim", None)
            cfg.pop("lon_dim", None)
            cfg.pop("coords_dim", None)
            cfg.pop("coords_order", None)

        # Assigner pour que model.clean() lise ces valeurs
        self.instance.config = cfg
        return cleaned

    def save(self, commit=True):
        obj: WidgetDef = super().save(commit=False)
        cfg = dict(obj.config or {})

        # commun
        cfg["title"] = (self.cleaned_data.get("title") or "").strip()
        cfg["metric"] = (self.cleaned_data.get("metric") or "").strip()
        cfg["x"] = (self.cleaned_data.get("x") or "").strip()
        cfg["agg"] = (self.cleaned_data.get("agg") or "sum").strip().lower()
        cfg["color"] = (self.cleaned_data.get("color") or "primary").strip()

        # map
        mm = (self.cleaned_data.get("map_mode") or "latlon").strip()
        cfg["map_mode"] = mm
        cfg["show_labels"] = bool(self.cleaned_data.get("show_labels"))
        if mm == "latlon":
            cfg["lat_dim"] = (self.cleaned_data.get("lat_dim") or "").strip()
            cfg["lon_dim"] = (self.cleaned_data.get("lon_dim") or "").strip()
            cfg.pop("coords_dim", None)
            cfg.pop("coords_order", None)
            cfg.pop("centroids", None)
        elif mm == "coords":
            cfg["coords_dim"] = (self.cleaned_data.get("coords_dim") or "").strip()
            cfg["coords_order"] = (self.cleaned_data.get("coords_order") or "latlon").strip().lower()
            cfg.pop("lat_dim", None)
            cfg.pop("lon_dim", None)
            cfg.pop("centroids", None)
        else:  # centroids
            cfg["x"] = (self.cleaned_data.get("x") or "").strip()
            cfg["centroids"] = self.cleaned_data.get("centroids") or {}
            cfg.pop("lat_dim", None)
            cfg.pop("lon_dim", None)
            cfg.pop("coords_dim", None)
            cfg.pop("coords_order", None)

        # TABLE helpers
        gd_text = (self.cleaned_data.get("group_dims_text") or "").strip()
        mt_text = (self.cleaned_data.get("metrics_text") or "").strip()
        cfg["group_dims_text"] = gd_text
        cfg["metrics_text"] = mt_text
        cfg["group_dims"] = _parse_group_dims_text(gd_text) if gd_text else []
        cfg["metrics"] = _parse_metrics_text(mt_text) if mt_text else []

        per = self.cleaned_data.get("per")
        cfg["per"] = int(per) if per else 25
        cfg["only_cols"] = (self.cleaned_data.get("only_cols") or "").strip()
        cfg["hide_cols"] = (self.cleaned_data.get("hide_cols") or "").strip()

        # nettoyage des vides (sauf per)
        for k in list(cfg.keys()):
            if cfg[k] in ("", None, []):
                if k == "per":
                    continue
                del cfg[k]

        obj.config = cfg
        if commit:
            obj.save()
        return obj


# =========================
# ExportDefForm
# =========================
class ExportDefForm(forms.ModelForm):
    group_dims_text = forms.CharField(
        required=False, label="Group dims (export)",
        help_text='Ex: province, departement'
    )
    metrics_text = forms.CharField(
        required=False, label="Metrics (export)",
        help_text='Ex: PPR:sum; PPCB:sum (séparées par ;)'
    )

    class Meta:
        model = ExportDef
        fields = ("view", "name", "format", "group_dims_text", "metrics_text", "filename_pattern", "config")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        cfg = self.instance.config or {}
        self.fields["group_dims_text"].initial = ", ".join(cfg.get("group_dims", []) or [])
        if "metrics_text" in cfg:
            metrics_text = cfg["metrics_text"]
        else:
            parts = []
            for m in (cfg.get("metrics") or []):
                parts.append(f"{(m.get('code') or '').strip()}:{(m.get('agg') or 'sum').strip().lower()}")
            metrics_text = "; ".join([p for p in parts if p and not p.endswith(":")])
        self.fields["metrics_text"].initial = metrics_text

    def save(self, commit=True):
        obj: ExportDef = super().save(commit=False)
        cfg = dict(obj.config or {})

        gd_text = (self.cleaned_data.get("group_dims_text") or "").strip()
        mt_text = (self.cleaned_data.get("metrics_text") or "").strip()

        cfg["group_dims_text"] = gd_text
        cfg["metrics_text"] = mt_text
        cfg["group_dims"] = _parse_group_dims_text(gd_text) if gd_text else []
        cfg["metrics"] = _parse_metrics_text(mt_text) if mt_text else []

        for k in list(cfg.keys()):
            if cfg[k] in ("", None, []):
                del cfg[k]

        obj.config = cfg
        if commit:
            obj.save()
        return obj
