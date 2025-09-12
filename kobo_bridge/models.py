from django.db import models

class KoboSource(models.Model):
    PULL,PUSH,BOTH = "pull","push","both"
    MODE_CHOICES = [(PULL,"Pull"),(PUSH,"Push"),(BOTH,"Both")]
    name = models.CharField(max_length=120, unique=True)
    server_url = models.URLField()
    asset_uid = models.CharField(max_length=64)
    token = models.CharField(max_length=255)
    mode = models.CharField(max_length=8, choices=MODE_CHOICES, default=BOTH)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        unique_together = ("server_url","asset_uid")
    def __str__(self): return f"{self.name} ({self.asset_uid})"

class RawSubmission(models.Model):
    source = models.ForeignKey(KoboSource, on_delete=models.CASCADE, related_name="submissions")
    instance_id = models.CharField(max_length=100)                  # meta/instanceID
    submission_id = models.CharField(max_length=50, null=True, blank=True) # _id
    xform_id = models.CharField(max_length=100, null=True, blank=True)
    form_version = models.CharField(max_length=100, null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField()                                    # JSON brut (aplati ou non)
    received_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["source", "instance_id"], name="uniq_source_instance")
        ]
        indexes = [
            models.Index(fields=["source", "instance_id"]),
            models.Index(fields=["submitted_at"]),
        ]