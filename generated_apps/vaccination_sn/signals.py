from __future__ import annotations
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import VaccinationSn
from Campagne.models import Campagne

def _norm_type(val: str | None) -> str:
    s = (val or "").strip().lower()
    # accepte "ciblée", "ciblee", etc.
    return "Ciblee" if s in {"ciblee", "ciblée"} else "Masse"

def _get_or_create_campaign(label: str, type_label: str) -> Campagne:
    label_stripped = (label or "").strip()
    # recherche case-insensitive
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

@receiver(post_save, sender=VaccinationSn)
def ensure_campaign_from_vaccination(sender, instance: VaccinationSn, created: bool, **kwargs):
    """
    À chaque save d'un parent VaccinationSn, garantir l'existence d'une Campagne
    pour le couple (Campagne, type_campagne) sans doublon.
    """
    label = (instance.campagne or "").strip()
    if not label:
        return
    typ = _norm_type(getattr(instance, "type_de_campagne", None))
    _get_or_create_campaign(label, typ)
