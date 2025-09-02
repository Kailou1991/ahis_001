# kobo_integration/models_base.py
from django.db import models

class KoboSubmissionBase(models.Model):
    # Identifiants/logs Kobo
    instance_id = models.CharField(max_length=128, db_index=True, blank=True, null=True)
    xform_id_string = models.CharField(max_length=200, blank=True, null=True)
    submission_time = models.DateTimeField(blank=True, null=True)
    submitted_by = models.CharField(max_length=150, blank=True, null=True)
    status = models.CharField(max_length=50, blank=True, null=True)
    version = models.CharField(max_length=64, blank=True, null=True)
    kobo_id = models.IntegerField(blank=True, null=True)
    uuid = models.CharField(max_length=255, blank=True, null=True)

    # objets/listes brutes Kobo
    validation_status = models.JSONField(blank=True, null=True)
    geojson = models.JSONField(blank=True, null=True)        # ex: _geolocation
    attachments = models.JSONField(blank=True, null=True)    # _attachments
    raw_json = models.JSONField(blank=True, null=True)       # row complet

    # horodatage local
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ("-id",)
