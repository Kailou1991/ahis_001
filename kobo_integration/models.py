# kobo_integration/models.py
from django.db import models
from django.utils import timezone
from django.contrib.auth.models import Group


# ---------- Connexion Kobo ----------
class KoboConnection(models.Model):
    name = models.CharField(max_length=100, unique=True)
    api_base = models.URLField(default="https://form.santeanimalechad.org")
    api_token = models.CharField(max_length=255)  # mets un champ chiffré si tu veux
    verify_ssl = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Connexion Kobo"
        verbose_name_plural = "Connexions Kobo"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # garantir l'unicité du « par défaut »
        if self.is_default:
            KoboConnection.objects.exclude(pk=self.pk).update(is_default=False)

    def __str__(self):
        return f"{self.name} ({self.api_base})"


# ---------- Formulaire Kobo (pilote le module généré) ----------
class KoboForm(models.Model):
    MODE_CHOICES = [("models", "MODELS"), ("jsonb", "JSONB")]

    name = models.CharField(max_length=150)
    xform_id_string = models.CharField(max_length=200, unique=True)
    version = models.CharField(max_length=64, blank=True)
    slug = models.SlugField(unique=True, help_text="Nom d'app: generated_apps/<slug>")
    secret_token = models.CharField(max_length=64)
    mode = models.CharField(max_length=16, choices=MODE_CHOICES, default="models")
    enabled = models.BooleanField(default=True)

    # droits d'accès au module
    allowed_groups = models.ManyToManyField(Group, blank=True)

    # parseur (chemin module:function)
    parser_path = models.CharField(max_length=255, blank=True)

    # liaison à une connexion Kobo choisie en admin
    connection = models.ForeignKey(
        KoboConnection, null=True, blank=True,
        on_delete=models.SET_NULL, related_name="forms",
        help_text="Connexion Kobo à utiliser pour ce formulaire"
    )

    # surcharges et caches pour la synchro (facultatifs)
    api_base = models.URLField(blank=True, default="", help_text="(Optionnel) Prioritaire sur la connexion")
    asset_uid = models.CharField(max_length=64, blank=True, help_text="UID du formulaire (aXXXX...) si connu")

    schema_json = models.JSONField(null=True, blank=True)
    sample_json = models.JSONField(null=True, blank=True)
    field_catalog_json = models.JSONField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Kobo form"
        verbose_name_plural = "Kobo forms"

    def __str__(self):
        return f"{self.name} ({self.xform_id_string})"

    # --- Résolution de la base/token/verify ---
    def resolve_api(self):
        """Renvoie (api_base, token, verify_ssl) avec priorités :
        champ du formulaire -> connexion liée -> connexion par défaut -> settings.
        """
        from django.conf import settings
        conn = self.connection or KoboConnection.objects.filter(is_default=True).first()

        base = (
            self.api_base
            or (conn.api_base if conn else None)
            or getattr(settings, "KOBO_API_BASE", "https://form.santeanimalechad.org")
        )
        token = (conn.api_token if conn else getattr(settings, "KOBO_TOKEN", None))
        verify = (conn.verify_ssl if conn else True)
        return base, token, verify


# ---------- Mapping Kobo -> modèle ----------
class KoboFieldMap(models.Model):
    form = models.ForeignKey(KoboForm, on_delete=models.CASCADE)
    kobo_name = models.CharField(max_length=255)     # ex: "Grp1/Date_signalement"
    model_field = models.CharField(max_length=255)   # ex: "date_signalement"
    dtype = models.CharField(
        max_length=64,
        help_text="string|integer|decimal|date|datetime|select|geo|image|file|boolean|json|repeat"
    )
    required = models.BooleanField(default=False)

    class Meta:
        unique_together = ("form", "kobo_name")
        ordering = ("form_id", "id")

    def __str__(self):
        return f"{self.form.slug}: {self.kobo_name} -> {self.model_field} ({self.dtype})"


# ---------- Journal des imports ----------
class SyncLog(models.Model):
    form = models.ForeignKey(KoboForm, on_delete=models.SET_NULL, null=True)
    instance_id = models.CharField(max_length=128, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=[(s, s) for s in ("RECEIVED", "IMPORTED", "SKIPPED", "FAILED")]
    )
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["instance_id"])]

    def __str__(self):
        return f"[{self.status}] {self.instance_id}"
