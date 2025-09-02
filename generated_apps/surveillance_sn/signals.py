# -*- coding: utf-8 -*-
from __future__ import annotations

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import SurveillanceSn as SParent
from .notifications import notify_new_suspicion

@receiver(post_save, sender=SParent)
def _surv_parent_created(sender, instance: SParent, created: bool, **kwargs):
    if created:
        transaction.on_commit(lambda: notify_new_suspicion(instance))
