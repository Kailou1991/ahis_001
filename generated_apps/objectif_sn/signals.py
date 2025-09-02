from __future__ import annotations
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import ObjectifSn
from Campagne.models import Campagne

def _norm_type(val: str | None) -> str:
    s = (val or "").strip().lower()
    return "Ciblee" if s in {"ciblee", "ciblée"} else "Masse"

def _get_or_create_campaign(label: str, type_label: str) -> Campagne:
    label_stripped = (label or "").strip()
    existing = Campagne.objects.filter(
        Campagne__iexact=label_stripped,
        type_campagne=type_label
    ).first()
    if existing:
        return existing
    return Campagne.objects.create(
        Campagne=label_stripped,
        type_campagne=type_label,
        statut=True,
    )

@receiver(post_save, sender=ObjectifSn)
def ensure_campaign_from_objectif(sender, instance: ObjectifSn, created: bool, **kwargs):
    """
    À chaque save d'un parent ObjectifSn, garantir l'existence d'une Campagne
    (couple unique Campagne/type_campagne).
    """
    label = (instance.campagne or "").strip()
    if not label:
        return
    typ = _norm_type(getattr(instance, "type_de_campagne", None))
    _get_or_create_campaign(label, typ)
