from __future__ import annotations

from django.contrib import admin, messages
from django.urls import path, reverse
from django.utils.html import format_html
from django.shortcuts import redirect
from django.http import JsonResponse
from django.db.models import Max

from .models import DatasetView, WidgetDef, ExportDef
from .admin_forms import WidgetDefForm, ExportDefForm
from .compute import prepare_query_metrics  # computed
from semantic_layer.models import Dimension, Measure, FilterDef


# ---------- Suggestions (pré-remplissage) ----------
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


class WidgetInline(admin.StackedInline):
    model = WidgetDef
    form = WidgetDefForm
    extra = 0
    fields = (
        "enabled", "order_idx", "type",
        "title", "metric", "x", "agg", "color",
        # --- MAP (dans config)
        "map_mode", "lat_dim", "lon_dim",
        "coords_dim", "coords_order",
        "centroids", "show_labels",
        # --- TABLE helpers
        "group_dims_text", "metrics_text", "per", "only_cols", "hide_cols",
    )
    show_change_link = True

    class Media:
        # Place le JS dans: static/publishing/admin/widgetdef_dynamic.js
        js = ("publishing/admin/widgetdef_dynamic.js",)

    # Injecter la view courante dans le form
    def get_formset(self, request, obj=None, **kwargs):
        form_class = self.form
        class InlineForm(form_class):
            VIEW_CTX = obj
        kwargs = dict(kwargs or {})
        kwargs["form"] = InlineForm
        return super().get_formset(request, obj, **kwargs)


class ExportInline(admin.StackedInline):
    model = ExportDef
    form = ExportDefForm
    extra = 0
    fields = ("name", "format", "group_dims_text", "metrics_text", "filename_pattern", "config")
    show_change_link = True


@admin.register(DatasetView)
class DatasetViewAdmin(admin.ModelAdmin):
    list_display = (
        "title", "slug", "dataset", "menu_title",
        "open_dash", "widgets_defaults_btn", "widgets_per_measure_btn",
        "publish_mv_btn", "refresh_mv_btn",
    )
    search_fields = ("title", "slug", "menu_title")
    list_filter = ("dataset",)
    fields = (
        "dataset", "slug", "title",
        "default_group_dims", "default_metrics", "visible_filters",
        "menu_title", "menu_icon",
        "computed_metrics",
    )
    inlines = [WidgetInline, ExportInline]

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
            path("<int:pk>/widgets_defaults/", self.admin_site.admin_view(self.widgets_defaults_view),
                 name="publishing_widgets_defaults"),
            path("<int:pk>/widgets_measures/", self.admin_site.admin_view(self.widgets_per_measure_view),
                 name="publishing_widgets_measures"),
            path("<int:pk>/publish_mv/", self.admin_site.admin_view(self.publish_mv_view),
                 name="publishing_publish_mv"),
            path("<int:pk>/refresh_mv/", self.admin_site.admin_view(self.refresh_mv_view),
                 name="publishing_refresh_mv"),
            path("suggest_from_dataset/<int:dataset_id>/", self.admin_site.admin_view(self.suggest_from_dataset_view),
                 name="publishing_suggest_from_dataset"),
        ]
        return custom + urls

    def suggest_from_dataset_view(self, request, dataset_id: int):
        return JsonResponse(_suggest_for_dataset(dataset_id))

    # --- Générations ---
    def widgets_defaults_view(self, request, pk):
        v = self.get_object(request, pk)
        time_dim = Dimension.objects.filter(dataset=v.dataset, is_time=True).order_by("code").first()
        any_dim  = Dimension.objects.filter(dataset=v.dataset).order_by("code").first()
        x_time = time_dim.code if time_dim else (any_dim.code if any_dim else None)
        non_time_dim = Dimension.objects.filter(dataset=v.dataset, is_time=False).order_by("code").first()
        x_cat = non_time_dim.code if non_time_dim else x_time

        if isinstance(v.default_metrics, list) and v.default_metrics:
            default_metric = (v.default_metrics[0] or {}).get("code")
        else:
            m0 = Measure.objects.filter(dataset=v.dataset).order_by("code").first()
            default_metric = m0.code if m0 else None

        created = 0
        next_idx = (v.widgets.aggregate(m=Max("order_idx"))["m"] or 0) + 1

        if x_time and default_metric and not v.widgets.filter(
            type="line", config__x=x_time, config__metric=default_metric
        ).exists():
            WidgetDef.objects.create(
                view=v, order_idx=next_idx, type="line", enabled=True,
                config={"x": x_time, "metric": default_metric, "agg": "sum",
                        "title": f"{default_metric} par {x_time}"}
            )
            next_idx += 1; created += 1

        if x_cat and default_metric and not v.widgets.filter(
            type="bar", config__x=x_cat, config__metric=default_metric
        ).exists():
            WidgetDef.objects.create(
                view=v, order_idx=next_idx, type="bar", enabled=True,
                config={"x": x_cat, "metric": default_metric, "agg": "sum",
                        "title": f"{default_metric} par {x_cat}"}
            )
            next_idx += 1; created += 1

        if not v.widgets.filter(type="table").exists():
            WidgetDef.objects.create(
                view=v, order_idx=next_idx, type="table", enabled=True,
                config={"group_dims": v.default_group_dims, "metrics": v.default_metrics}
            )
            created += 1

        messages.success(request, f"Widgets par défaut : {created} créé(s).")
        return redirect("admin:publishing_datasetview_change", pk)

    def widgets_per_measure_view(self, request, pk):
        v = self.get_object(request, pk)
        measures = list(Measure.objects.filter(dataset=v.dataset).order_by("code"))
        time_dim = Dimension.objects.filter(dataset=v.dataset, is_time=True).order_by("code").first()
        palette = ["primary", "success", "info", "warning", "danger", "secondary"]
        next_idx = (v.widgets.aggregate(m=Max("order_idx"))["m"] or 0) + 1
        created = 0
        for i, m in enumerate(measures):
            if not v.widgets.filter(type="kpi_card", config__metric=m.code).exists():
                WidgetDef.objects.create(
                    view=v, order_idx=next_idx, type="kpi_card", enabled=True,
                    config={"metric": m.code, "agg": (m.default_agg or "sum").lower(),
                            "title": m.label or m.code, "color": palette[i % len(palette)]}
                )
                next_idx += 1; created += 1

            if time_dim and not v.widgets.filter(
                type="line", config__metric=m.code, config__x=time_dim.code
            ).exists():
                WidgetDef.objects.create(
                    view=v, order_idx=next_idx, type="line", enabled=False,
                    config={"x": time_dim.code, "metric": m.code, "agg": (m.default_agg or "sum").lower(),
                            "title": f"{m.label or m.code} par {time_dim.label or time_dim.code}"}
                )
                next_idx += 1; created += 1

        messages.success(request, f"{created} widget(s) généré(s) pour les mesures.")
        return redirect("admin:publishing_datasetview_change", pk)

    # --- MV (urls ci-dessus) ---
    def publish_mv_view(self, request, pk):
        try:
            from .mv import create_or_replace_mv_for_view
        except Exception as e:
            messages.error(request, f"Import MV échoué: {e}")
            return redirect("admin:publishing_datasetview_change", pk)

        v = self.get_object(request, pk)
        try:
            name = create_or_replace_mv_for_view(v)
            messages.success(request, f"Materialized View créée : {name}")
        except Exception as e:
            messages.error(request, f"Échec MV : {e}")
        return redirect("admin:publishing_datasetview_change", pk)

    def refresh_mv_view(self, request, pk):
        try:
            from .mv import refresh_mv
        except Exception as e:
            messages.error(request, f"Import refresh MV échoué: {e}")
            return redirect("admin:publishing_datasetview_change", pk)

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


@admin.register(WidgetDef)
class WidgetDefAdmin(admin.ModelAdmin):
    form = WidgetDefForm
    list_display = ("view", "order_idx", "type", "enabled", "display_title", "metric_from_cfg", "x_from_cfg")
    list_filter = ("view", "type", "enabled")
    list_editable = ("enabled",)
    search_fields = ("config",)
    actions = ("action_enable", "action_disable")
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

    class Media:
        js = ("publishing/admin/widgetdef_dynamic.js",)

    # Endpoint JSON pour Ajax choices si besoin ailleurs
    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "choices_for_view/<int:view_id>/",
                self.admin_site.admin_view(self.choices_for_view),
                name="publishing_widget_choices_for_view",
            ),
        ]
        return custom + urls

    def choices_for_view(self, request, view_id: int):
        try:
            v = DatasetView.objects.get(pk=view_id)
        except DatasetView.DoesNotExist:
            return JsonResponse({"measures": [], "dimensions": []})

        measures = [{"value": m.code, "label": (m.label or m.code)}
                    for m in Measure.objects.filter(dataset=v.dataset).order_by("code")]
        dimensions = [{"value": d.code, "label": (d.label or d.code)}
                      for d in Dimension.objects.filter(dataset=v.dataset).order_by("code")]

        try:
            _, comp_defs, _ = prepare_query_metrics(v, include_view_defaults=True)
            for c in comp_defs:
                code = c.get("code")
                label = c.get("title") or c.get("label") or code
                if not code:
                    continue
                if c.get("kind") == "measure":
                    measures.append({"value": code, "label": f"{label} (computed)"})
                elif c.get("kind") == "dimension":
                    dimensions.append({"value": code, "label": f"{label} (computed)"})
        except Exception:
            pass

        return JsonResponse({"measures": measures, "dimensions": dimensions})

    # Pré-remplir ?view=<id>
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

    def get_form(self, request, obj=None, **kwargs):
        form_class = self.form
        class AdminForm(form_class):
            VIEW_CTX = getattr(obj, "view", None) if obj else None
        kwargs = dict(kwargs or {})
        kwargs["form"] = AdminForm
        return super().get_form(request, obj, **kwargs)


@admin.register(ExportDef)
class ExportDefAdmin(admin.ModelAdmin):
    form = ExportDefForm
    list_display = ("view", "name", "format", "filename_pattern")
    list_filter = ("view", "format")
    search_fields = ("name", "filename_pattern", "config")
    fields = ("view", "name", "format", "group_dims_text", "metrics_text", "filename_pattern", "config")
