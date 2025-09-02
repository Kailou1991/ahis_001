# -*- coding: utf-8 -*-
from __future__ import annotations
from django.apps import AppConfig

class SurveillanceSnConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "generated_apps.surveillance_sn"

    def ready(self):
        from . import signals  # noqa: F401
