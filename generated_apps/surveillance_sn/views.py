# generated_apps/surveillance_sn/views.py
from __future__ import annotations

from django.views.generic import ListView, DetailView
from django.http import JsonResponse, Http404
from django.db.models import Sum, Value, Q
from django.db.models.functions import Coalesce

from .models import (
    SurveillanceSn as SParent,
    SurveillanceSnChild783b28ae as SChild,
)

# --- NEW: helper pour récupérer les noms région/département depuis la session (IDs -> libellés Kobo) ---
def _session_region_dept_names(request):
    region_name = depart_name = None
    try:
        region_id = request.session.get('region_id')
        depart_id = request.session.get('departement_id')
        if region_id:
            from Region.models import Region
            region_name = Region.objects.filter(id=region_id).values_list("Nom", flat=True).first()
        if depart_id:
            from Departement.models import Departement
            depart_name = Departement.objects.filter(id=depart_id).values_list("Nom", flat=True).first()
    except Exception:
        pass
    return region_name, depart_name


class SurveillanceStats(ListView):
    """
    Liste à plat des items 'grp6_items' (une ligne = un item enfant),
    Filtres: période (date signalement), région, maladie, recherche libre.
    + Totaux (troupeau, malades, morts).

    ⚠️ Restreint automatiquement au périmètre session (admin régional/départemental).
    """
    model = SChild
    template_name = "surveillance_sn/stats.html"
    context_object_name = "rows"
    paginate_by = 50

    # ----- helpers -----
    def _base_queryset(self):
        qs = (
            SChild.objects
            .select_related("parent")
            .order_by("-parent__submission_time", "-parent_id", "item_index")
        )
        # Restreindre par session
        region_name, depart_name = _session_region_dept_names(self.request)
        if region_name:
            qs = qs.filter(parent__grp3_region__iexact=region_name)
        if depart_name:
            qs = qs.filter(parent__grp3_departement__iexact=depart_name)
        return qs

    def _apply_filters(
        self, qs,
        d_from: str | None, d_to: str | None,
        region: str | None, maladie: str | None, query: str | None
    ):
        # Fenêtre temporelle sur la date de signalement
        if d_from:
            qs = qs.filter(parent__grp1_date_signalement__gte=d_from)
        if d_to:
            qs = qs.filter(parent__grp1_date_signalement__lte=d_to)

        # NB: ces filtres s'ajoutent AU-DESSUS du périmètre session
        if region:
            qs = qs.filter(parent__grp3_region__iexact=region)

        if maladie:
            qs = qs.filter(parent__grp5_qmad1__icontains=maladie)

        if query:
            q = query.strip()
            if q:
                qs = qs.filter(
                    Q(parent__commentaire_de_la_suspicion__icontains=q) |
                    Q(parent__grp5_liste_signes__icontains=q) |
                    Q(parent__grp5_liste_lesions__icontains=q) |
                    Q(parent__grp5_evolutionmaladie__icontains=q) |
                    Q(parent__grp3_lieususpicion__icontains=q) |
                    Q(parent__grp3_nom_du_village__icontains=q) |
                    Q(parent__grp3_commune__icontains=q)
                )
        return qs

    # ----- hooks -----
    def get_queryset(self):
        qs = self._base_queryset()
        d_from  = (self.request.GET.get("d_from") or "").strip()
        d_to    = (self.request.GET.get("d_to") or "").strip()
        region  = (self.request.GET.get("region") or "").strip()
        maladie = (self.request.GET.get("maladie") or "").strip()
        query   = (self.request.GET.get("q") or "").strip()
        return self._apply_filters(qs, d_from, d_to, region, maladie, query)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # Filtres courants
        d_from  = (self.request.GET.get("d_from") or "").strip()
        d_to    = (self.request.GET.get("d_to") or "").strip()
        region  = (self.request.GET.get("region") or "").strip()
        maladie = (self.request.GET.get("maladie") or "").strip()
        query   = (self.request.GET.get("q") or "").strip()

        qs = self.get_queryset()

        # Totaux (gère les variantes de champ)
        agg = qs.aggregate(
            total_troupeau = Sum(Coalesce("totaltroupeau", "effectif_total_troup_st_de_tot")),
            total_malades  = Sum("total_malade"),
            total_morts    = Sum(Coalesce("effectif_animaux_morts_calcule", "calcul_animaux_morts")),
        )
        ctx["totals"] = {
            "rows": qs.count(),
            "troupeau": int(agg["total_troupeau"] or 0),
            "malades":  int(agg["total_malades"] or 0),
            "morts":    int(agg["total_morts"] or 0),
        }

        # Listes déroulantes (déjà restreintes au périmètre session via _base_queryset)
        base = self._base_queryset()
        ctx["regions"] = (
            base.exclude(parent__grp3_region__isnull=True)
                .exclude(parent__grp3_region="")
                .values_list("parent__grp3_region", flat=True)
                .distinct().order_by("parent__grp3_region")
        )
        ctx["maladies"] = (
            base.exclude(parent__grp5_qmad1__isnull=True)
                .exclude(parent__grp5_qmad1="")
                .values_list("parent__grp5_qmad1", flat=True)
                .distinct().order_by("parent__grp5_qmad1")
        )

        # Filtres “sticky”
        ctx["filters"] = {
            "d_from": d_from, "d_to": d_to,
            "region": region, "maladie": maladie,
            "q": query,
        }
        return ctx


class SurveillanceDetail(DetailView):
    """
    Détail d’un foyer (parent) + items enfants + totaux.

    ⚠️ Protégé par le périmètre session: 404 si l’objet n’appartient pas
       à la région/département de l’utilisateur (sauf super admin sans périmètre).
    """
    model = SParent
    template_name = "surveillance_sn/detail.html"
    context_object_name = "foyer"

    # NEW: protège l'accès par périmètre session
    def get_queryset(self):
        qs = super().get_queryset()
        region_name, depart_name = _session_region_dept_names(self.request)
        if region_name:
            qs = qs.filter(grp3_region__iexact=region_name)
        if depart_name:
            qs = qs.filter(grp3_departement__iexact=depart_name)
        return qs

    def get_object(self, queryset=None):
        # Assure le 404 si hors périmètre
        obj = super().get_object(queryset)
        region_name, depart_name = _session_region_dept_names(self.request)
        if region_name and (obj.grp3_region or "").strip().lower() != region_name.strip().lower():
            raise Http404("Objet hors périmètre régional.")
        if depart_name and (obj.grp3_departement or "").strip().lower() != depart_name.strip().lower():
            raise Http404("Objet hors périmètre départemental.")
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        parent = self.object

        enfants = parent.grp6_items.order_by("item_index").all()

        # Totaux agrégés sur les enfants
        agg = enfants.aggregate(
            troupeau = Sum(Coalesce("totaltroupeau", "effectif_total_troup_st_de_tot")),
            malades  = Sum("total_malade"),
            morts    = Sum(Coalesce("effectif_animaux_morts_calcule", "calcul_animaux_morts")),
            f_adult  = Sum("fadultes"),
            f_jeunes = Sum("fjeunes"),
            m_adult  = Sum("madultes"),
            m_jeunes = Sum("mjeunes"),
        )

        ctx["enfants"] = enfants
        ctx["child_totals"] = {k: int(v or 0) for k, v in agg.items()}
        return ctx
