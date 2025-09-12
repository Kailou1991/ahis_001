from django.contrib import admin, messages
from django import forms
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import redirect
from django.http import JsonResponse
from django.db.models import Max
from django.db.models import Max, Q   # <-- ajouter Q ici
from .models import DatasetView, WidgetDef, ExportDef
from .admin_forms import WidgetDefForm
from semantic_layer.models import Dimension, Measure, FilterDef
from .compute import prepare_query_metrics


# ---------- Suggestions (pré-remplissage automatique à partir du dataset) ----------
def _suggest_for_dataset(dataset_id: int):
    dims_qs = list(Dimension.objects.filter(dataset_id=dataset_id).order_by("code"))
    meas_qs = list(Measure.objects.filter(dataset_id=dataset_id).order_by("code"))
    filt_qs = list(FilterDef.objects.filter(dataset_id=dataset_id).order_by("code"))

    dim_codes = [d.code for d in dims_qs]
    ordered_dims = [c for c in ("date", "region", "maladie") if c in dim_codes]
    ordered_dims += [c for c in dim_codes if c not in ordered_dims]

    metrics = [{"code": m.code, "agg": (m.default_agg or "sum").lower()} for m in meas_qs]

    filt_codes = [f.code for f in filt_qs]
    ordered_filters = [c for c in ("periode", "region", "maladie") if c in filt_codes]
    ordered_filters += [c for c in filt_codes if c not in ordered_filters]

    return {
        "default_group_dims": (ordered_dims[:3] or ordered_dims),
        "default_metrics": (metrics[:2] or metrics),
        "visible_filters": (ordered_filters[:5] or ordered_filters),
    }


# ---------- Helpers de fusion de vues existantes ----------
def _view_metadata(view: DatasetView):
    """Dims/filters/metrics + computed exposés par une vue."""
    group_dims = list(getattr(view, "default_group_dims", []) or [])
    visible_filters = list(getattr(view, "visible_filters", []) or [])
    raw_metrics = list(getattr(view, "default_metrics", []) or [])

    # computed exposés par la vue via compute (source de vérité)
    _, comp_defs, _ = prepare_query_metrics(view, include_view_defaults=True)
    computed_measures = [c for c in comp_defs if c.get("kind") == "measure"]
    computed_dims     = [c for c in comp_defs if c.get("kind") == "dimension"]

    return {
        "slug": view.slug,
        "title": view.title,
        "group_dims": group_dims,
        "visible_filters": visible_filters,
        "metrics_full": raw_metrics,  # [{code, agg}]
        "computed_measures": computed_measures,
        "computed_dims": computed_dims,
    }


def _merge_view_metadata(meta_list):
    """Fusionne plusieurs métadonnées en dédoublonnant, conserve l’ordre d’apparition."""
    def _uniq(seq):
        seen, out = set(), []
        for x in seq:
            if x not in seen:
                seen.add(x); out.append(x)
        return out

    group_dims = _uniq([d for m in meta_list for d in m.get("group_dims", [])])
    visible_filters = _uniq([f for m in meta_list for f in m.get("visible_filters", [])])

    # metrics_full: garder le premier agg rencontré par code
    metrics_full_map = {}
    for m in meta_list:
        for spec in m.get("metrics_full", []):
            if not spec:
                continue
            code = spec.get("code")
            if not code:
                continue
            metrics_full_map.setdefault(code, {
                "code": code,
                "agg": (spec.get("agg") or "sum").lower(),
            })
    metrics_full = list(metrics_full_map.values())

    # computed fusionnés par code
    def _merge(kind_key):
        out = {}
        for m in meta_list:
            for c in m.get(kind_key, []):
                code = c.get("code")
                if code and code not in out:
                    out[code] = c
        return list(out.values())

    computed_measures = _merge("computed_measures")
    computed_dims     = _merge("computed_dims")

    return {
        "group_dims": group_dims,
        "visible_filters": visible_filters,
        "metrics_full": metrics_full,
        "computed_measures": computed_measures,
        "computed_dims": computed_dims,
    }


# ---------- Parseur des "recettes" de métriques calculées (mini DSL) ----------
def _parse_computed_recipes(text: str):
    """
    Parse des lignes du type:
      code = expr [; title="..."] [; round=N]
    - 'code' : identifiant (slug-like)
    - 'expr' : expression arithmétique utilisant des codes de métriques
    - 'title' (optionnel)
    - 'round' (optionnel, entier)
    Retour: liste de dicts {code, kind='measure', expr, title?, round?}
    """
    out = []
    if not text:
        return out
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        left, right = line.split("=", 1)
        code = (left or "").strip()
        if not code:
            continue
        # split expr ; k=v ; k=v
        parts = [p.strip() for p in right.split(";") if p.strip()]
        if not parts:
            continue
        expr = parts[0]
        meta = {"title": None, "round": None}
        for p in parts[1:]:
            if "=" not in p:
                continue
            k, v = p.split("=", 1)
            k = k.strip().lower(); v = v.strip()
            if k == "title":
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                meta["title"] = v
            elif k == "round":
                try:
                    meta["round"] = int(v)
                except Exception:
                    pass
        safe_code = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in code)
        item = {"code": safe_code, "kind": "measure", "expr": expr.strip()}
        if meta["title"]:
            item["title"] = meta["title"]
        if meta["round"] is not None:
            item["round"] = meta["round"]
        out.append(item)
    return out


# ---------- Form admin universel pour DatasetView ----------
class DatasetViewAdminForm(forms.ModelForm):
    # Sélection de vues existantes comme sources de pré-remplissage
    prefill_from = forms.ModelMultipleChoiceField(
        queryset=DatasetView.objects.none(),
        required=False,
        label="Pré-remplir depuis d’autres vues",
        help_text="Sélectionnez une ou plusieurs vues (ex: vaccination, objectif) pour fusionner dims/filters/métriques."
    )
    # Saisie rapide de slugs
    prefill_slugs = forms.CharField(
        required=False,
        label="Ou coller des slugs (séparés par des virgules)",
        help_text="Ex: vaccination_td_test, objectif_td_2025"
    )
    # Éditeur générique de métriques calculées
    computed_recipes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "style": "font-family:monospace"}),
        label="Métriques calculées (recettes)",
        help_text=(
            'Une ligne par métrique: code = expression [; title="..."] [; round=N]. '
            'Ex: taux_realisation = (doses * 100) / objectif ; title="Taux (%)" ; round=1'
        ),
    )

    class Meta:
        model = DatasetView
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        qs = DatasetView.objects.all()
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        self.fields["prefill_from"].queryset = qs.order_by("title", "slug")

        # Pré-remplir l’éditeur avec l’existant (si la vue possède déjà des computed)
        exist = list(getattr(self.instance, "computed_metrics", []) or [])
        if exist:
            lines = []
            for c in exist:
                if (c or {}).get("kind") != "measure":
                    continue
                code = c.get("code") or ""
                expr = c.get("expr") or ""
                title = c.get("title")
                rnd = c.get("round")
                extra = []
                if title:
                    extra.append(f'title="{title}"')
                if isinstance(rnd, int):
                    extra.append(f"round={rnd}")
                suffix = (" ; " + " ; ".join(extra)) if extra else ""
                if code and expr and not self.data:
                    lines.append(f"{code} = {expr}{suffix}")
            if lines and not self.data:
                self.fields["computed_recipes"].initial = "\n".join(lines)

    # Collecte des vues à fusionner depuis les champs du form
    def _collect_prefill_sources(self):
        slugs_text = (self.cleaned_data.get("prefill_slugs") or "").strip()
        extra_slugs = [s.strip() for s in slugs_text.split(",") if s.strip()] if slugs_text else []
        selected = list(self.cleaned_data.get("prefill_from") or [])
        return list(
    DatasetView.objects.filter(
        Q(pk__in=[v.pk for v in selected]) |   # <-- ici
        Q(slug__in=extra_slugs)                # <-- et ici
    ).distinct()
)

    def merge_into_fields(self):
        """
        Fusionne dims/filters/metrics de vues sources dans les champs du formulaire (sans enregistrer),
        puis applique les recettes 'computed_recipes' pour générer des metrics calculées génériques.
        """
        # 1) Fusion simple
        sources = self._collect_prefill_sources()
        if sources:
            metas = [_view_metadata(v) for v in sources]
            merged = _merge_view_metadata(metas)
            self.cleaned_data["default_group_dims"] = merged["group_dims"]
            self.cleaned_data["visible_filters"] = merged["visible_filters"]
            self.cleaned_data["default_metrics"] = merged["metrics_full"]

        # 2) Appliquer l’éditeur de recettes -> computed_metrics (universel)
        recipes_text = (self.cleaned_data.get("computed_recipes") or "").strip()
        new_computed = _parse_computed_recipes(recipes_text)

        # Conserver d’éventuels computed existants hors recettes (si édition)
        current = list(getattr(self.instance, "computed_metrics", []) or [])
        replace_codes = {c["code"] for c in new_computed}
        kept = [c for c in current if c.get("code") not in replace_codes]
        final = kept + new_computed

        self.cleaned_data["computed_metrics"] = final


# ---------- Inlines ----------
class WidgetInline(admin.TabularInline):
    model = WidgetDef
    form = WidgetDefForm
    extra = 0
    fields = (
        "enabled", "order_idx", "type", "title",
        "metric", "x", "agg", "color",
        "group_dims_text", "metrics_text", "per", "only_cols", "hide_cols",
    )
    show_change_link = True

    # Injecte la DatasetView (obj) dans le formulaire via une sous-classe dynamique
    def get_formset(self, request, obj=None, **kwargs):
        form_class = self.form
        class InlineForm(form_class):
            VIEW_CTX = obj  # la DatasetView en édition
        kwargs = dict(kwargs or {})
        kwargs["form"] = InlineForm
        return super().get_formset(request, obj, **kwargs)


class ExportInline(admin.TabularInline):
    model = ExportDef
    extra = 0
    fields = ("name", "format", "config", "filename_pattern")
    show_change_link = True


# ---------- Admin DatasetView ----------
@admin.register(DatasetView)
class DatasetViewAdmin(admin.ModelAdmin):
    form = DatasetViewAdminForm

    list_display = (
        "title",
        "slug",
        "dataset",
        "menu_title",
        "open_dash",
        "widgets_defaults_btn",
        "widgets_per_measure_btn",
        "publish_mv_btn",
        "refresh_mv_btn",
        "table_only_cols",
        "table_hidden_cols",
    )
    search_fields = ("title", "slug", "menu_title")
    list_filter = ("dataset",)

    # On insère les 2 champs de pré-remplissage + l’éditeur de recettes dans le formulaire admin
    fields = (
        # --- Pré-remplissage multi-vues + recettes (form-only fields) ---
        "prefill_from",
        "prefill_slugs",
        "computed_recipes",
        # --- Champs du modèle ---
        "dataset",
        "slug",
        "title",
        "default_group_dims",
        "default_metrics",
        "visible_filters",
        "menu_title",
        "menu_icon",
        "computed_metrics",  # JSONField avec les métriques calculées effectives
    )
    inlines = [WidgetInline, ExportInline]

    # Pré-remplissage si ADD ouvert avec ?dataset=<id>
    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        ds_id = request.GET.get("dataset")
        if ds_id and ds_id.isdigit():
            try:
                initial.update(_suggest_for_dataset(int(ds_id)))
                initial["dataset"] = int(ds_id)
            except Exception:
                pass
        return initial

    # --- Boutons ---
    @admin.display(description="Dashboard")
    def open_dash(self, obj):
        url = reverse("publishing:view_detail", args=[obj.slug])
        return format_html('<a class="button" href="{}" target="_blank">Ouvrir</a>', url)

    @admin.display(description="Widgets défaut")
    def widgets_defaults_btn(self, obj):
        url = reverse("admin:publishing_widgets_defaults", args=[obj.pk])
        return format_html('<a class="button" href="{}">Créer</a>', url)

    @admin.display(description="Widgets par mesure")
    def widgets_per_measure_btn(self, obj):
        url = reverse("admin:publishing_widgets_measures", args=[obj.pk])
        return format_html('<a class="button" href="{}">Générer</a>', url)

    @admin.display(description="Publier MV")
    def publish_mv_btn(self, obj):
        url = reverse("admin:publishing_publish_mv", args=[obj.pk])
        return format_html('<a class="button" href="{}">Publier</a>', url)

    @admin.display(description="Rafraîchir MV")
    def refresh_mv_btn(self, obj):
        if getattr(obj, "materialized_name", None):
            url = reverse("admin:publishing_refresh_mv", args=[obj.pk])
            return format_html('<a class="button" href="{}">Rafraîchir</a>', url)
        return "-"

    # --- Routes customs ---
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pk>/widgets_defaults/",
                self.admin_site.admin_view(self.widgets_defaults_view),
                name="publishing_widgets_defaults",
            ),
            path(
                "<int:pk>/widgets_measures/",
                self.admin_site.admin_view(self.widgets_per_measure_view),
                name="publishing_widgets_measures",
            ),
            path(
                "<int:pk>/publish_mv/",
                self.admin_site.admin_view(self.publish_mv_view),
                name="publishing_publish_mv",
            ),
            path(
                "<int:pk>/refresh_mv/",
                self.admin_site.admin_view(self.refresh_mv_view),
                name="publishing_refresh_mv",
            ),
            path(
                "suggest_from_dataset/<int:dataset_id>/",
                self.admin_site.admin_view(self.suggest_from_dataset_view),
                name="publishing_suggest_from_dataset",
            ),
        ]
        return custom + urls

    def suggest_from_dataset_view(self, request, dataset_id: int):
        return JsonResponse(_suggest_for_dataset(dataset_id))

    # --- Générations ---
    def widgets_defaults_view(self, request, pk):
        v = self.get_object(request, pk)
        time_dim = (
            Dimension.objects.filter(dataset=v.dataset, is_time=True)
            .order_by("code")
            .first()
        )
        any_dim = Dimension.objects.filter(dataset=v.dataset).order_by("code").first()
        x_time = time_dim.code if time_dim else (any_dim.code if any_dim else None)
        non_time_dim = (
            Dimension.objects.filter(dataset=v.dataset, is_time=False)
            .order_by("code")
            .first()
        )
        x_cat = non_time_dim.code if non_time_dim else x_time

        default_metric = None
        if isinstance(v.default_metrics, list) and v.default_metrics:
            default_metric = (v.default_metrics[0] or {}).get("code")
        if not default_metric:
            m0 = Measure.objects.filter(dataset=v.dataset).order_by("code").first()
            default_metric = m0.code if m0 else None

        created = 0
        next_idx = (v.widgets.aggregate(m=Max("order_idx"))["m"] or 0) + 1

        if (
            x_time
            and default_metric
            and not v.widgets.filter(
                type="line", config__x=x_time, config__metric=default_metric
            ).exists()
        ):
            WidgetDef.objects.create(
                view=v,
                order_idx=next_idx,
                type="line",
                enabled=True,
                config={
                    "x": x_time,
                    "metric": default_metric,
                    "agg": "sum",
                    "title": f"{default_metric} par {x_time}",
                },
            )
            next_idx += 1
            created += 1

        if (
            x_cat
            and default_metric
            and not v.widgets.filter(
                type="bar", config__x=x_cat, config__metric=default_metric
            ).exists()
        ):
            WidgetDef.objects.create(
                view=v,
                order_idx=next_idx,
                type="bar",
                enabled=True,
                config={
                    "x": x_cat,
                    "metric": default_metric,
                    "agg": "sum",
                    "title": f"{default_metric} par {x_cat}",
                },
            )
            next_idx += 1
            created += 1

        if not v.widgets.filter(type="table").exists():
            WidgetDef.objects.create(
                view=v,
                order_idx=next_idx,
                type="table",
                enabled=True,
                config={
                    "group_dims": v.default_group_dims,
                    "metrics": v.default_metrics,
                },
            )
            created += 1

        messages.success(request, f"Widgets par défaut : {created} créé(s).")
        return redirect("admin:publishing_datasetview_change", pk)

    def widgets_per_measure_view(self, request, pk):
        v = self.get_object(request, pk)
        measures = list(Measure.objects.filter(dataset=v.dataset).order_by("code"))
        time_dim = (
            Dimension.objects.filter(dataset=v.dataset, is_time=True)
            .order_by("code")
            .first()
        )
        palette = ["primary", "success", "info", "warning", "danger", "secondary"]
        next_idx = (v.widgets.aggregate(m=Max("order_idx"))["m"] or 0) + 1
        created = 0
        for i, m in enumerate(measures):
            if not v.widgets.filter(type="kpi_card", config__metric=m.code).exists():
                WidgetDef.objects.create(
                    view=v,
                    order_idx=next_idx,
                    type="kpi_card",
                    enabled=True,
                    config={
                        "metric": m.code,
                        "agg": (m.default_agg or "sum").lower(),
                        "title": m.label or m.code,
                        "color": palette[i % len(palette)],
                    },
                )
                next_idx += 1
                created += 1
            if time_dim and not v.widgets.filter(
                type="line", config__metric=m.code, config__x=time_dim.code
            ).exists():
                WidgetDef.objects.create(
                    view=v,
                    order_idx=next_idx,
                    type="line",
                    enabled=False,  # par défaut masqué
                    config={
                        "x": time_dim.code,
                        "metric": m.code,
                        "agg": (m.default_agg or "sum").lower(),
                        "title": f"{m.label or m.code} par {time_dim.label or time_dim.code}",
                    },
                )
                next_idx += 1
                created += 1
        messages.success(request, f"{created} widget(s) généré(s) pour les mesures.")
        return redirect("admin:publishing_datasetview_change", pk)

    def publish_mv_view(self, request, pk):
        from .mv import create_or_replace_mv_for_view
        v = self.get_object(request, pk)
        try:
            name = create_or_replace_mv_for_view(v)
            messages.success(request, f"Materialized View créée : {name}")
        except Exception as e:
            messages.error(request, f"Échec MV : {e}")
        return redirect("admin:publishing_datasetview_change", pk)

    def refresh_mv_view(self, request, pk):
        from .mv import refresh_mv
        v = self.get_object(request, pk)
        if not getattr(v, "materialized_name", None):
            messages.error(request, "Aucune MV publiée pour cette vue.")
        else:
            try:
                refresh_mv(v.materialized_name)
                messages.success(request, "Materialized View rafraîchie.")
            except Exception as e:
                messages.error(request, f"Échec refresh : {e}")
        return redirect("admin:publishing_datasetview_change", pk)

    # --- Hook d’enregistrement: applique la fusion + recettes si demandée ---
    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get("prefill_from") or form.cleaned_data.get("prefill_slugs") or form.cleaned_data.get("computed_recipes"):
            form.merge_into_fields()
            obj.default_group_dims = form.cleaned_data.get("default_group_dims", obj.default_group_dims)
            obj.visible_filters = form.cleaned_data.get("visible_filters", obj.visible_filters)
            obj.default_metrics = form.cleaned_data.get("default_metrics", obj.default_metrics)
            if form.cleaned_data.get("computed_metrics") is not None:
                obj.computed_metrics = form.cleaned_data["computed_metrics"]
        super().save_model(request, obj, form, change)


# ---------- Admin WidgetDef ----------
@admin.register(WidgetDef)
class WidgetDefAdmin(admin.ModelAdmin):
    form = WidgetDefForm
    list_display = (
        "view",
        "order_idx",
        "type",
        "enabled",
        "display_title",
        "metric_from_cfg",
        "x_from_cfg",
    )
    list_filter = ("view", "type", "enabled")
    list_editable = ("enabled",)
    search_fields = ("config",)
    actions = ("action_enable", "action_disable")

    # Champs explicitement alignés avec le formulaire (inclut 'view')
    fields = (
        "view", "enabled", "order_idx", "type",
        "title", "metric", "x", "agg", "color",
        "group_dims_text", "metrics_text", "per", "only_cols", "hide_cols",
    )

    # Pré-remplir ?view=<id> en création hors inline
    def get_changeform_initial_data(self, request):
        initial = super().get_changeform_initial_data(request)
        vid = request.GET.get("view")
        if vid:
            initial["view"] = vid
        return initial

    @admin.display(description="Titre")
    def display_title(self, obj):
        return (obj.config or {}).get("title") or ""

    @admin.display(description="Métrique")
    def metric_from_cfg(self, obj):
        return (obj.config or {}).get("metric") or ""

    @admin.display(description="X")
    def x_from_cfg(self, obj):
        return (obj.config or {}).get("x") or ""

    def action_enable(self, request, queryset):
        n = queryset.update(enabled=True)
        self.message_user(request, f"{n} widget(s) activé(s).", level=messages.SUCCESS)
    action_enable.short_description = "Activer la sélection"

    def action_disable(self, request, queryset):
        n = queryset.update(enabled=False)
        self.message_user(request, f"{n} widget(s) masqué(s).", level=messages.SUCCESS)
    action_disable.short_description = "Masquer la sélection"

    # Injecte la view dans le form en édition directe (hors inline)
    def get_form(self, request, obj=None, **kwargs):
        form_class = self.form
        class AdminForm(form_class):
            VIEW_CTX = getattr(obj, "view", None) if obj else None
        kwargs = dict(kwargs or {})
        kwargs["form"] = AdminForm
        return super().get_form(request, obj, **kwargs)
