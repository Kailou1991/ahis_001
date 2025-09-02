# -*- coding: utf-8 -*-
from __future__ import annotations

import unicodedata
from typing import Dict, Iterable, Tuple, Set, List

from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction
from django.db import models

# Modèles cibles
from Region.models import Region
from Departement.models import Departement
from Commune.models import Commune


# ----------------------
# Normalisation / clés
# ----------------------
BAD_TOKENS = {"", "-", "—", "n/a", "na", "aucune", "none", "null"}

def _clean(s: str | None) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).strip()
    s = " ".join(s.split())
    return s

def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")

def norm_key(s: str | None) -> str:
    s = _clean(s)
    if not s:
        return ""
    return _strip_accents(s).casefold()


# ----------------------
# Collecte depuis apps
# ----------------------
def _is_text_field(field: models.Field) -> bool:
    return isinstance(field, (models.CharField, models.TextField))

def _pick_field(model: type[models.Model], needle: str) -> str | None:
    needle = needle.lower()
    for f in model._meta.get_fields():
        if isinstance(f, models.Field) and _is_text_field(f) and needle in f.name.lower():
            return f.name
    return None

def _values_distinct(qs, *field_names: str):
    """Valeurs distinctes non nulles / non vides."""
    for f in field_names:
        qs = qs.filter(**{f"{f}__isnull": False}).exclude(**{f: ""})
    return qs.values_list(*field_names).distinct()

def extract_triplets_from_app(app_label: str) -> Set[Tuple[str, str | None, str | None]]:
    """
    Set de (region, departement|None, commune|None) collectés sur tous les modèles de l'app.
    """
    out: set[Tuple[str, str | None, str | None]] = set()
    try:
        appconf = apps.get_app_config(app_label)
    except LookupError:
        return out

    for Model in appconf.get_models():
        try:
            r = _pick_field(Model, "region")
            d = _pick_field(Model, "depart")
            c = _pick_field(Model, "commune")
            if not any([r, d, c]):
                continue

            base = Model.objects.all()

            if r and d and c:
                for reg, dep, com in _values_distinct(base, r, d, c):
                    reg = _clean(reg); dep = _clean(dep); com = _clean(com)
                    if reg.casefold() in BAD_TOKENS: continue
                    out.add((reg, dep or None, com or None))
                continue

            if r and d:
                for reg, dep in _values_distinct(base, r, d):
                    reg = _clean(reg); dep = _clean(dep)
                    if reg.casefold() in BAD_TOKENS: continue
                    out.add((reg, dep or None, None))
                continue

            if r:
                for reg, in _values_distinct(base, r):
                    reg = _clean(reg)
                    if reg.casefold() in BAD_TOKENS: continue
                    out.add((reg, None, None))
                continue
        except Exception:
            # On ignore un modèle bruyant sans planter la commande
            continue
    return out


# ----------------------
# Upsert hiérarchique
# ----------------------
def preload_maps() -> tuple[Dict[str, Region], Dict[tuple[str, str], Departement], Dict[tuple[str, str, str], bool]]:
    # Regions
    r_map: Dict[str, Region] = {norm_key(r.Nom): r for r in Region.objects.all()}

    # Départements
    d_map: Dict[tuple[str, str], Departement] = {}
    for d in Departement.objects.select_related("Region").all():
        if d.Region_id:
            d_map[(norm_key(d.Region.Nom), norm_key(d.Nom))] = d

    # Communes (utilisation bool pour alléger)
    c_map: Dict[tuple[str, str, str], bool] = {}
    for c in Commune.objects.select_related("DepartementID", "DepartementID__Region").all():
        if c.DepartementID_id and c.DepartementID.Region_id:
            c_map[(norm_key(c.DepartementID.Region.Nom), norm_key(c.DepartementID.Nom), norm_key(c.Nom))] = True

    return r_map, d_map, c_map


def upsert_hierarchy(triplets: Iterable[Tuple[str, str | None, str | None]]) -> tuple[int, int, int]:
    r_map, d_map, c_map = preload_maps()
    created_r = created_d = created_c = 0

    # Nettoyage + tri SAFE (None -> "")
    cleaned: List[Tuple[str, str | None, str | None]] = []
    for reg, dep, com in triplets:
        reg_c = _clean(reg)
        if not reg_c or reg_c.casefold() in BAD_TOKENS:
            continue
        dep_c = _clean(dep) if dep else None
        com_c = _clean(com) if com else None
        cleaned.append((reg_c, dep_c, com_c))

    def sort_key(t: Tuple[str, str | None, str | None]) -> tuple[str, str, str]:
        return (norm_key(t[0]), norm_key(t[1] or ""), norm_key(t[2] or ""))

    with transaction.atomic():
        for reg, dep, com in sorted(cleaned, key=sort_key):
            rkey = norm_key(reg)
            region_obj = r_map.get(rkey)
            if not region_obj:
                region_obj = Region.objects.create(Nom=reg)
                r_map[rkey] = region_obj
                created_r += 1

            if dep:
                dkey = (rkey, norm_key(dep))
                dep_obj = d_map.get(dkey)
                if not dep_obj:
                    dep_obj = Departement.objects.create(Nom=dep, Region=region_obj)
                    d_map[dkey] = dep_obj
                    created_d += 1

                if com:
                    ckey = (rkey, dkey[1], norm_key(com))
                    if ckey not in c_map:
                        Commune.objects.create(Nom=com, DepartementID=dep_obj)
                        c_map[ckey] = True
                        created_c += 1

    return created_r, created_d, created_c


# ----------------------
# Commande
# ----------------------
class Command(BaseCommand):
    help = "Peuple Region/Departement/Commune depuis surveillance_sn, vaccination_sn, objectif_sn (sans doublons)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apps",
            nargs="*",
            default=["surveillance_sn", "vaccination_sn", "objectif_sn"],
            help="Liste d'apps à scanner (défaut: surveillance_sn vaccination_sn objectif_sn)"
        )

    def handle(self, *args, **opts):
        apps_to_scan = opts["apps"]
        self.stdout.write(self.style.MIGRATE_HEADING("→ Scan des sources: " + ", ".join(apps_to_scan)))

        triplets: set[Tuple[str, str | None, str | None]] = set()

        # 1) surveillance_sn (champs connus)
        try:
            SParent = apps.get_model("surveillance_sn", "SurveillanceSn")
            vals = (SParent.objects
                    .filter(grp3_region__isnull=False).exclude(grp3_region="")
                    .values_list("grp3_region", "grp3_departement", "grp3_commune")
                    .distinct())
            for reg, dep, com in vals:
                reg = _clean(reg); dep = _clean(dep); com = _clean(com)
                if reg.casefold() in BAD_TOKENS: continue
                triplets.add((reg, dep or None, com or None))
            self.stdout.write(f"  surveillance_sn: {len(vals)} combinaisons trouvées.")
        except LookupError:
            self.stdout.write("  surveillance_sn: app introuvable (ok).")

        # 2) autres apps (heuristique texte)
        for app_label in apps_to_scan:
            if app_label == "surveillance_sn":
                continue
            extra = extract_triplets_from_app(app_label)
            if extra:
                self.stdout.write(f"  {app_label}: {len(extra)} combinaisons.")
            triplets |= extra

        # 3) upsert hiérarchique
        r, d, c = upsert_hierarchy(triplets)
        self.stdout.write(self.style.SUCCESS(f"✓ Créés: Regions={r}, Departements={d}, Communes={c}"))
        self.stdout.write(self.style.HTTP_INFO("Terminé."))
