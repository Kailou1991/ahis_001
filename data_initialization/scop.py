# accounts/scope.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from typing import Optional
from django.db.models import Q
from django.contrib.auth.models import Group

def _is_sysadmin(user) -> bool:
    return bool(user and (user.is_superuser or user.groups.filter(name__iexact="Administrateur Système").exists()))

def _get_session_area_names(request) -> tuple[Optional[str], Optional[str]]:
    """
    Convertit les IDs en session -> libellés (Nom) pour filtrer
    les modèles *sans FK* (ex. SurveillanceSn: grp3_region/grp3_departement).
    """
    region_id = request.session.get("region_id")
    departement_id = request.session.get("departement_id")
    region_name = depart_name = None
    if region_id:
        try:
            from Region.models import Region
            region_name = Region.objects.filter(id=region_id).values_list("Nom", flat=True).first()
        except Exception:
            region_name = None
    if departement_id:
        try:
            from Departement.models import Departement
            depart_name = Departement.objects.filter(id=departement_id).values_list("Nom", flat=True).first()
        except Exception:
            depart_name = None
    return region_name, depart_name


# -------------------------------
# 1) Filtre pour modèles avec FK
# -------------------------------
def scope_q_fk(request, *, region_field: str = "region", departement_field: str = "departement") -> Q:
    """
    Construit un Q() à appliquer sur un queryset dont le modèle possède
    des FKs 'region' et/ou 'departement' (ex. Foyer, etc.).
    - Admin Système / superuser : aucun filtre
    - Admin Départemental : filtre par departement_id
    - Admin Régional : filtre par region_id
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or _is_sysadmin(user):
        return Q()  # pas de restriction

    region_id = request.session.get("region_id")
    departement_id = request.session.get("departement_id")

    # Admin Départemental prioritaire
    if user.groups.filter(name__iexact="Administrateur Départemental").exists() and departement_id:
        return Q(**{f"{departement_field}_id": departement_id})

    # Admin Régional
    if user.groups.filter(name__iexact="Administrateur Régional").exists() and region_id:
        return Q(**{f"{region_field}_id": region_id})

    # Par défaut, pas de filtre si rien en session
    return Q()


# -------------------------------------
# 2) Filtre pour modèles *sans* FK (Kobo)
# -------------------------------------
def scope_q_text(request, *, region_text_field: str = "grp3_region", departement_text_field: str = "grp3_departement") -> Q:
    """
    Construit un Q() pour les modèles où la région/département sont des *textes*
    (ex. SurveillanceSn: grp3_region / grp3_departement).
    """
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated or _is_sysadmin(user):
        return Q()

    region_name, depart_name = _get_session_area_names(request)

    if user.groups.filter(name__iexact="Administrateur Départemental").exists() and depart_name:
        return Q(**{f"{departement_text_field}__iexact": depart_name})

    if user.groups.filter(name__iexact="Administrateur Régional").exists() and region_name:
        return Q(**{f"{region_text_field}__iexact": region_name})

    return Q()
