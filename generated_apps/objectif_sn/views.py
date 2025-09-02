from collections import defaultdict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.views.generic import ListView

from .models import ObjectifSn, ObjectifSnChild0c8ff1d1


class ObjectifStats(LoginRequiredMixin, ListView):
    """
    Liste à plat des enregistrements enfant (une ligne = une commune/maladie dans un item repeat),
    avec filtres (campagne, maladie, région, département) et totaux en en-tête.
    """
    model = ObjectifSnChild0c8ff1d1
    template_name = "objectif_sn/stats_objectifs.html"
    context_object_name = "rows"
    paginate_by = 50

    # --------- helpers ---------
    def _base_queryset(self):
        return (
            ObjectifSnChild0c8ff1d1.objects
            .select_related("parent")
            .order_by("-parent__submission_time", "-parent_id", "item_index")
        )

    def _region_dept_map(self):
        """
        Construit un mapping {region: [departements triés]} à partir des parents.
        Sert au double filtre + au dropdown dépendant côté template.
        """
        q = (
            ObjectifSn.objects
            .exclude(grp4_region__isnull=True).exclude(grp4_region="")
            .exclude(grp4_departement__isnull=True).exclude(grp4_departement="")
            .values_list("grp4_region", "grp4_departement")
            .distinct()
        )
        acc = defaultdict(set)
        for region, dept in q:
            acc[region].add(dept)
        return {r: sorted(ds) for r, ds in acc.items()}

    # --------- queryset avec filtres ---------
    def get_queryset(self):
        qs = self._base_queryset()

        campagne = self.request.GET.get("campagne", "").strip()
        maladie  = self.request.GET.get("maladie", "").strip()
        region   = self.request.GET.get("region", "").strip()
        dept     = self.request.GET.get("departement", "").strip()

        if campagne:
            qs = qs.filter(parent__campagne__icontains=campagne)
        if maladie:
            qs = qs.filter(maladie_masse__icontains=maladie)
        if region:
            qs = qs.filter(parent__grp4_region__icontains=region)
        if dept:
            qs = qs.filter(parent__grp4_departement__icontains=dept)

        return qs

    # --------- contexte ---------
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs = self.get_queryset()

        # Totaux
        agg = qs.aggregate(
            cible=Sum("effectif_cible"),
            elligible=Sum("effectif_elligible"),
        )
        cible = agg["cible"] or 0
        elligible = agg["elligible"] or 0
        taux_elig = (elligible / cible * 100.0) if cible else 0.0

        ctx["totals"] = {
            "rows": qs.count(),
            "cible": cible,
            "elligible": elligible,
            "taux_elig": taux_elig,
        }

        # Valeurs distinctes pour alimenter les filtres
        ctx["campaigns"] = (
            ObjectifSn.objects.exclude(campagne__isnull=True)
                              .exclude(campagne="")
                              .values_list("campagne", flat=True)
                              .distinct().order_by("campagne")
        )
        ctx["maladies"] = (
            ObjectifSnChild0c8ff1d1.objects.exclude(maladie_masse__isnull=True)
                                           .exclude(maladie_masse="")
                                           .values_list("maladie_masse", flat=True)
                                           .distinct().order_by("maladie_masse")
        )

        # régions / départements (avec dépendance Région → Départements)
        region_dept_map = self._region_dept_map()
        selected_region = self.request.GET.get("region", "").strip()
        if selected_region and selected_region in region_dept_map:
            deps = region_dept_map[selected_region]
        else:
            # tous les départements uniques si aucune région sélectionnée
            all_deps = set()
            for dlist in region_dept_map.values():
                all_deps.update(dlist)
            deps = sorted(all_deps)

        ctx["regions"] = sorted(region_dept_map.keys())
        ctx["departements"] = deps
        ctx["region_dept_map"] = region_dept_map  # pour le JS (json_script)

        # filtres “sticky”
        ctx["filters"] = {
            "campagne": self.request.GET.get("campagne", "").strip(),
            "maladie": self.request.GET.get("maladie", "").strip(),
            "region": selected_region,
            "departement": self.request.GET.get("departement", "").strip(),
        }
        return ctx
