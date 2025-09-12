from django.db import models
from django.utils import timezone

# ===========================
# 1) Jeu de données logique
# ===========================
class DatasetLogical(models.Model):
    name = models.CharField(max_length=150, unique=True)
    source = models.ForeignKey("kobo_bridge.KoboSource", on_delete=models.CASCADE)
    description = models.TextField(blank=True, default="")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# ===========================
# 2) Dimensions (admin-driven)
# ===========================
class Dimension(models.Model):
    DTYPE_CHOICES = [
        ("text", "Texte"),
        ("date", "Date"),
        ("code", "Code"),
        ("geo", "Géographie"),
    ]

    dataset = models.ForeignKey(DatasetLogical, on_delete=models.CASCADE, related_name="dimensions")
    code = models.CharField(max_length=80)                 # ex: date, region, dept, commune, maladie, espece
    label = models.CharField(max_length=200)
    path = models.CharField(max_length=255)                # ex: "Grp_loc/code_commune"
    dtype = models.CharField(max_length=20, choices=DTYPE_CHOICES, default="text")
    transform = models.CharField(max_length=80, blank=True, null=True)  # ex: to_date, first_in_array
    # IMPORTANT: paramètres pour le transform (lecture de listes, sous-champs, etc.)
    transform_params = models.JSONField(default=dict, blank=True)
    is_time = models.BooleanField(default=False)
    is_geo = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ("dataset", "code")
        ordering = ["dataset", "code"]
        indexes = [
            models.Index(fields=["dataset", "code"]),
        ]

    def __str__(self) -> str:
        return f"{self.dataset.name}::{self.code}"


# ===========================
# 3) Mesures (admin-driven)
# ===========================
class Measure(models.Model):
    SUM, COUNT, AVG, MIN, MAX = "sum", "count", "avg", "min", "max"
    AGG_CHOICES = [(SUM, "sum"), (COUNT, "count"), (AVG, "avg"), (MIN, "min"), (MAX, "max")]

    dataset = models.ForeignKey(DatasetLogical, on_delete=models.CASCADE, related_name="measures")
    code = models.CharField(max_length=80)                 # ex: nb_malades
    label = models.CharField(max_length=200)
    path = models.CharField(max_length=255)                # ex: "Grp6/total_malade" (ou chemin de liste)
    transform = models.CharField(max_length=80, blank=True, null=True)  # ex: sum_array_field_number, derive_sum
    # IMPORTANT: paramètres pour le transform (champ interne, sources, etc.)
    transform_params = models.JSONField(default=dict, blank=True)
    default_agg = models.CharField(max_length=10, choices=AGG_CHOICES, default=SUM)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ("dataset", "code")
        ordering = ["dataset", "code"]
        indexes = [
            models.Index(fields=["dataset", "code"]),
        ]

    def __str__(self) -> str:
        return f"{self.dataset.name}::{self.code}"


# ===========================
# 4) Filtres (admin-driven)
# ===========================
class FilterDef(models.Model):
    OP_CHOICES = [
        ("in", "IN (liste)"),
        ("eq", "Égal"),
        ("between", "Entre (dates/nombres)"),
        ("gte", ">= (min)"),
        ("lte", "<= (max)"),
        ("contains", "Contient (texte)"),
    ]

    dataset = models.ForeignKey(DatasetLogical, on_delete=models.CASCADE, related_name="filters")
    code = models.CharField(max_length=80)                 # ex: periode, maladie, region
    label = models.CharField(max_length=200)
    dim_code = models.CharField(max_length=80)             # dimension ciblée
    op = models.CharField(max_length=16, choices=OP_CHOICES, default="in")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ("dataset", "code")
        ordering = ["dataset", "code"]
        indexes = [
            models.Index(fields=["dataset", "code"]),
        ]

    def __str__(self) -> str:
        return f"{self.dataset.name}::{self.code} ({self.op})"


# ===========================
# 5) Table générique des lignes analytiques
# ===========================
class WideRow(models.Model):
    """
    Optionnel: table générique "lignes analytiques".
    - dims: {"date":"2025-01-02","region":"ML-1","maladie":"PPR", ...}
    - meas: {"nb_malades": 12, "nb_morts": 1}
    """
    dataset = models.ForeignKey(DatasetLogical, on_delete=models.CASCADE, related_name="widerows")
    source = models.ForeignKey("kobo_bridge.KoboSource", on_delete=models.CASCADE)
    instance_id = models.CharField(max_length=100)
    submitted_at = models.DateTimeField(null=True, blank=True)
    dims = models.JSONField(default=dict, blank=True)
    meas = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        unique_together = ("dataset", "instance_id")
        ordering = ["-submitted_at", "dataset"]
        indexes = [
            models.Index(fields=["dataset", "submitted_at"]),
            models.Index(fields=["dataset", "instance_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.dataset.name}::{self.instance_id}"
