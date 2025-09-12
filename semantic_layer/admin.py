# semantic_layer/admin.py
import json
from django.contrib import admin, messages
from django.urls import path, reverse, NoReverseMatch
from django.utils.html import format_html
from django.shortcuts import redirect
from django import forms
from django.template.response import TemplateResponse

from .models import DatasetLogical, Dimension, Measure, FilterDef, WideRow
from .services import (
    parse_json_payload, analyze_json_records, create_mapping_from_suggestions,
    detect_repeat_candidates, rebuild_widerows_for_dataset
)

class ImportJsonForm(forms.Form):
    json_text = forms.CharField(
        label="Collez ici un échantillon JSON",
        widget=forms.Textarea(attrs={"rows": 18, "style": "width:100%; font-family:monospace;"}),
        help_text="Un tableau JSON (ou un objet unique)."
    )
    dry_run = forms.BooleanField(label="Simulation (ne pas enregistrer)", required=False, initial=False)
    explode_all_repeats = forms.BooleanField(label="Déplier toutes les répétitions détectées", required=False, initial=False)
    code_case = forms.ChoiceField(
        label="Format de code",
        choices=[("keep","Conserver"),("snake","snake_case"),("kebab","kebab-case"),("camel","camelCase"),("pascal","PascalCase")],
        initial="keep"
    )
    rename_map = forms.CharField(
        label="Renommage des codes (JSON facultatif)",
        required=False,
        widget=forms.Textarea(attrs={"rows": 6, "style": "width:100%; font-family:monospace;"}),
        help_text='Ex.: {"DateVaccination":"date","grpInfoGlobalVaccination/grpInfoSiteVaccination/effectifTotalAnimauxVaccinesParSite":"vaccines"}'
    )

@admin.register(DatasetLogical)
class DatasetLogicalAdmin(admin.ModelAdmin):
    list_display = (
        "name", "source", "active", "created_at",
        "widerow_count", "mapping_link", "rebuild_btn", "create_view_link", "import_json_btn",
    )
    list_filter = ("active", "source")
    search_fields = ("name", "description")
    ordering = ("name",)

    @admin.display(description="Lignes analytiques")
    def widerow_count(self, obj):
        return WideRow.objects.filter(dataset=obj).count()

    @admin.display(description="Mapping assisté")
    def mapping_link(self, obj):
        try:
            url = reverse("semantic:mapping", args=[obj.pk])
            return format_html('<a class="button" target="_blank" href="{}">Ouvrir</a>', url)
        except NoReverseMatch:
            return format_html('<span style="color:#999">Route "semantic:mapping" absente</span>')

    @admin.display(description="Rebuild WideRow")
    def rebuild_btn(self, obj):
        url = reverse("admin:semantic_rebuild", args=[obj.pk])
        return format_html('<a class="button" href="{}">Rebuild</a>', url)

    @admin.display(description="Créer une Vue")
    def create_view_link(self, obj):
        try:
            url = reverse("admin:publishing_datasetview_add") + f"?dataset={obj.pk}"
            return format_html('<a class="button" href="{}">Créer</a>', url)
        except NoReverseMatch:
            return format_html('<span style="color:#999">Routes publishing absentes</span>')

    @admin.display(description="Importer JSON")
    def import_json_btn(self, obj):
        url = reverse("admin:semantic_import_json", args=[obj.pk])
        return format_html('<a class="button" href="{}">Importer</a>', url)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path("<int:pk>/rebuild/", self.admin_site.admin_view(self.rebuild_view), name="semantic_rebuild"),
            path("<int:pk>/import_json/", self.admin_site.admin_view(self.import_json_view), name="semantic_import_json"),
        ]
        return custom + urls

    def rebuild_view(self, request, pk):
        ds = self.get_object(request, pk)
        rebuild_widerows_for_dataset(ds)
        messages.success(request, "WideRow reconstruit.")
        return redirect("admin:semantic_layer_datasetlogical_change", pk)

    def import_json_view(self, request, pk):
        ds: DatasetLogical = self.get_object(request, pk)
        context = dict(self.admin_site.each_context(request), title=f"Importer JSON — {ds.name}", dataset=ds)
        if request.method == "POST":
            form = ImportJsonForm(request.POST)
            context["form"] = form
            if form.is_valid():
                try:
                    records = parse_json_payload(form.cleaned_data["json_text"])
                    # candidats répétitions (détection)
                    repeat_candidates = detect_repeat_candidates(records)
                    context["repeat_candidates"] = repeat_candidates

                    # sélection utilisateur des répétitions à déplier
                    selected_repeat_paths = request.POST.getlist("repeat_paths")
                    if form.cleaned_data.get("explode_all_repeats"):
                        selected_repeat_paths = repeat_candidates

                    # map de renommage
                    rename_map = {}
                    if form.cleaned_data.get("rename_map"):
                        try:
                            #rename_map = json.loads(form.cleaned_data["rename_map"])
                            from semantic_layer.services import safe_json_loads
                            rename_map = safe_json_loads(form.cleaned_data["rename_map"])
                        except Exception:
                            messages.warning(request, "rename_map invalide: JSON ignoré.")

                    sugg = analyze_json_records(
                        records,
                        expand_repeat_paths=selected_repeat_paths,
                        rename_map=rename_map,
                        code_case=form.cleaned_data.get("code_case") or "keep",
                    )

                    context["suggestions"] = sugg
                    context["selected_repeat_paths"] = set(selected_repeat_paths)

                    if form.cleaned_data.get("dry_run"):
                        messages.info(request, f"Simulation → dimensions:{len(sugg['dimensions'])} mesures:{len(sugg['measures'])} filtres:{len(sugg['filters'])}")
                    else:
                        res = create_mapping_from_suggestions(ds, sugg)
                        messages.success(request, f"Créé/MàJ → Dimensions:{res['dimensions']} Mesures:{res['measures']} Filtres:{res['filters']}")
                        return redirect("admin:semantic_layer_datasetlogical_change", pk)

                except Exception as e:
                    messages.error(request, f"Échec import: {e}")
        else:
            default_json = '[{"DateVaccination":"2025-01-01","region":"ML-1","cercle":"...","commune":"...","vaccines":123}]'
            form = ImportJsonForm(initial={"json_text": default_json})
            context["form"] = form

        return TemplateResponse(request, "admin/semantic_layer/import_json.html", context)


@admin.register(Dimension)
class DimensionAdmin(admin.ModelAdmin):
    list_display = ("dataset", "code", "label", "dtype", "is_time", "is_geo", "created_at")
    list_filter = ("dataset", "dtype", "is_time", "is_geo")
    search_fields = ("code", "label", "path", "transform")
    ordering = ("dataset", "code")


@admin.register(Measure)
class MeasureAdmin(admin.ModelAdmin):
    list_display = ("dataset", "code", "label", "default_agg", "created_at")
    list_filter = ("dataset", "default_agg")
    search_fields = ("code", "label", "path", "transform")
    ordering = ("dataset", "code")


@admin.register(FilterDef)
class FilterDefAdmin(admin.ModelAdmin):
    list_display = ("dataset", "code", "dim_code", "op", "created_at")
    list_filter = ("dataset", "op")
    search_fields = ("code", "label", "dim_code")
    ordering = ("dataset", "code")


@admin.register(WideRow)
class WideRowAdmin(admin.ModelAdmin):
    list_display = ("dataset", "instance_id", "submitted_at", "created_at")
    list_filter = ("dataset",)
    date_hierarchy = "submitted_at"
    search_fields = ("instance_id",)
    ordering = ("-submitted_at",)
