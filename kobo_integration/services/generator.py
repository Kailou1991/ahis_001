# kobo_integration/services/generator.py
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import keyword
import hashlib
import logging
import time
import importlib.util
from typing import Dict, List, Tuple, Any, DefaultDict, Optional
from collections import defaultdict

from django.template import engines
from django.conf import settings
from django.db import transaction, connection
from django.utils.text import slugify

from kobo_integration.models import KoboForm, KoboFieldMap
import requests

logger = logging.getLogger(__name__)
engine = engines["django"]

# -------------------- Types simples (hors repeat) --------------------
TYPE_MAP: Dict[str, str] = {
    "string":   "models.TextField(blank=True, null=True)",  # <= au lieu de CharField(255)
    "integer":  "models.IntegerField(blank=True, null=True)",
    "decimal":  "models.DecimalField(max_digits=20, decimal_places=6, blank=True, null=True)",
    "date":     "models.DateField(blank=True, null=True)",
    "datetime": "models.DateTimeField(blank=True, null=True)",
    "boolean":  "models.BooleanField(blank=True, null=True)",
    "select":   "models.CharField(max_length=120, blank=True, null=True)",
    "geo":      "models.JSONField(blank=True, null=True)",
    "image":    "models.TextField(blank=True, null=True)",
    "file":     "models.TextField(blank=True, null=True)",
    "json":     "models.JSONField(blank=True, null=True)",
}

RESERVED_MODEL_FIELD_NAMES = {"id"}

# Champs système du parent qu'on garde toujours
SYSTEM_PARENT_FIELDS = {
    "instance_id", "xform_id_string", "submission_time", "submitted_by",
    "status", "geojson", "raw_json", "created_at", "updated_at"
}

# -------------------- Helpers --------------------
def _reset_migrations(app_dir: Path):
    mig = app_dir / "migrations"
    mig.mkdir(parents=True, exist_ok=True)
    init = mig / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")
    for p in mig.glob("[0-9][0-9][0-9][0-9]_*.py"):
        p.unlink()
    for p in mig.glob("[0-9][0-9][0-9][0-9]_*.pyc"):
        p.unlink()

def _project_pkg() -> str:
    return settings.ROOT_URLCONF.split(".")[0]

def _settings_py_path() -> Path:
    return Path(settings.BASE_DIR) / _project_pkg() / "settings.py"

def _ensure_generated_apps_pkg():
    root = Path(settings.BASE_DIR) / "generated_apps"
    root.mkdir(parents=True, exist_ok=True)
    init = root / "__init__.py"
    if not init.exists():
        init.write_text("", encoding="utf-8")

def ensure_app_declared_in_settings(app_slug: str) -> bool:
    sp = _settings_py_path()
    txt = sp.read_text(encoding="utf-8")
    app_full = f"generated_apps.{app_slug}"
    if f"'{app_full}'" in txt or f'"{app_full}"' in txt:
        return False
    txt += f"\n# auto-added by AHIS generator\nINSTALLED_APPS += ['{app_full}']\n"
    sp.write_text(txt, encoding="utf-8")
    return True

def run_manage(*args: str) -> str:
    manage_py = Path(settings.BASE_DIR) / "manage.py"
    cmd = [sys.executable, str(manage_py), *args]
    p = subprocess.run(cmd, cwd=str(settings.BASE_DIR), capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(
            f"manage.py {' '.join(args)} failed:\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        )
    return p.stdout

def model_name_from_slug(slug: str) -> str:
    return "".join(p.capitalize() for p in re.split(r"[^a-z0-9]+", slug) if p)

def detect_existing_model_name(app_dir: Path) -> Optional[str]:
    models_py = app_dir / "models.py"
    if models_py.exists():
        for line in models_py.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", line)
            if m:
                return m.group(1)
    return None

def camelize(name: str) -> str:
    parts = [p for p in re.split(r"[^0-9a-zA-Z]+", name) if p]
    return "".join(p[:1].upper() + p[1:] for p in parts)

def form_class_name_for(model_name: str) -> str:
    return f"{model_name}Form"

def canon_name(raw: str, used: set[str]) -> str:
    s = (raw or "").strip()
    s = s.replace("/", "_")
    s = re.sub(r"[^\w]+", "_", s)
    s = re.sub(r"__+", "_", s).strip("_").lower()
    if not s or not re.match(r"[a-z_]", s[0]):
        s = f"f_{s or 'field'}"
    if s in RESERVED_MODEL_FIELD_NAMES or keyword.iskeyword(s):
        s = f"kobo_{s}"
    base = s
    i = 1
    while s in used or s in SYSTEM_PARENT_FIELDS:
        s = f"{base}_{i}"
        i += 1
    return s

def _guess_dtype(val: Any) -> str:
    if val is None:
        return "string"
    if isinstance(val, bool):
        return "boolean"
    if isinstance(val, int):
        return "integer"
    if isinstance(val, float):
        return "decimal"
    if isinstance(val, (list, dict)):
        return "json"
    if isinstance(val, str):
        vs = val.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", vs):
            return "date"
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z?", vs):
            return "datetime"
        if vs.lower() in {"true", "false"}:
            return "boolean"
        if re.fullmatch(r"-?\d+", vs):
            return "integer"
        if re.fullmatch(r"-?\d+(\.\d+)?", vs):
            return "decimal"
        return "string"
    return "string"

def _existing_maps(form: KoboForm) -> List[dict]:
    return list(
        KoboFieldMap.objects.filter(form=form)
        .order_by("kobo_name")
        .values("id", "kobo_name", "model_field", "dtype")
    )

def _repeat_prefixes_from_sample_dict(sample: Optional[dict]) -> set[str]:
    out: set[str] = set()
    if not isinstance(sample, dict):
        return out
    for k, v in sample.items():
        if isinstance(v, list) and (not v or any(isinstance(x, dict) for x in v if x is not None)):
            out.add(k)
    return out

def _fetch_one_submission(form: KoboForm) -> Optional[dict]:
    base, token, verify = form.resolve_api()
    uid = form.asset_uid or form.xform_id_string
    if not uid or not base:
        return None
    url = f"{base.rstrip('/')}/assets/{uid}/submissions/?format=json&page_size=1"
    headers = {"Authorization": f"Token {token}"} if token else {}
    try:
        r = requests.get(url, headers=headers, verify=verify, timeout=60)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data[0] if data else None
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return data["results"][0] if data["results"] else None
    except Exception as e:
        logger.error(f"Error fetching submission sample: {e}")
        return None
    return None

@transaction.atomic
def _ensure_maps_from_sample_if_missing(form: KoboForm) -> List[dict]:
    maps = _existing_maps(form)
    if maps:
        return maps

    sample = form.sample_json if isinstance(form.sample_json, dict) else None
    if not sample:
        sample = _fetch_one_submission(form)
    if not isinstance(sample, dict) or not sample:
        return maps

    repeats = _repeat_prefixes_from_sample_dict(sample)

    new_maps: List[KoboFieldMap] = []
    seen: set[Tuple[str, str]] = set()

    def _add_map(kobo_name: str, dtype: str, model_field: Optional[str] = None):
        key = (kobo_name, dtype)
        if key in seen:
            return
        seen.add(key)
        mf = canon_name(model_field or kobo_name.replace("/", "_"), set())
        new_maps.append(KoboFieldMap(form=form, kobo_name=kobo_name, model_field=mf, dtype=dtype))

    for k, v in sample.items():
        if k.startswith("_"):
            continue
        if k.endswith("_count"):
            _add_map(k, "integer")
            continue
        if isinstance(v, list) and k in repeats:
            _add_map(k, "repeat", model_field=k)
            example = next((x for x in v if isinstance(x, dict)), None)
            if example:
                for ck, cv in example.items():
                    suffix = ck.split("/", 1)[1] if "/" in ck else ck
                    _add_map(f"{k}/{suffix}", _guess_dtype(cv), model_field=suffix)
            continue
        _add_map(k, _guess_dtype(v))

    KoboFieldMap.objects.bulk_create(new_maps, ignore_conflicts=True)
    return _existing_maps(form)

def _generate_table_name(app_slug: str, model_name: str) -> str:
    """Génère un nom de table court et stable (max 63 caractères pour PostgreSQL)"""
    base_name = f"{app_slug}_{slugify(model_name).replace('-', '_')}"
    base_name = base_name.lower()
    if len(base_name) <= 63:
        return base_name
    hash_id = hashlib.md5(base_name.encode()).hexdigest()[:12]
    short_app_slug = app_slug[:10] if len(app_slug) > 10 else app_slug
    return f"{short_app_slug}_{hash_id}".lower()

def _generate_child_class_name(model_name: str, prefix: str) -> str:
    """Génère un nom de classe enfant court et stable"""
    prefix_id = hashlib.md5(prefix.encode()).hexdigest()[:8]
    return f"{model_name}Child{prefix_id}"

def _table_exists(table_name: str) -> bool:
    """Vérifie si une table existe dans la base de données"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_tables WHERE tablename = %s)", [table_name])
        return cursor.fetchone()[0]

def _create_table_with_schema_editor(model_class):
    """Crée une table directement avec le schema editor si nécessaire"""
    from django.db import connection
    with connection.schema_editor() as schema_editor:
        schema_editor.create_model(model_class)

def _create_empty_migration(app_dir: Path, app_slug: str):
    """Crée une migration vide pour forcer la détection des modèles"""
    mig_dir = app_dir / "migrations"
    mig_dir.mkdir(exist_ok=True)
    if any(mig_dir.glob("*.py")):
        return
    timestamp = time.strftime("%Y%m%d_%H%M")
    migration_file = mig_dir / f"{timestamp}_initial.py"
    migration_file.write_text(
        "from django.db import migrations\n\n"
        "class Migration(migrations.Migration):\n"
        "    initial = True\n\n"
        "    dependencies = []\n\n"
        "    operations = []\n",
        encoding="utf-8"
    )
    return migration_file

def _load_model_class(app_slug: str, model_name: str):
    """
    Charge dynamiquement la classe de modèle **sans recharger** le module si déjà importé,
    afin d'éviter le warning 'Model ... was already registered'.
    """
    app_label = f"generated_apps.{app_slug}"
    module_name = f"{app_label}.models"
    module_path = Path(settings.BASE_DIR) / "generated_apps" / app_slug / "models.py"

    # ✅ Ne pas ré-exécuter le module si déjà chargé
    if module_name in sys.modules:
        module = sys.modules[module_name]
    else:
        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sys.modules[module_name] = module

    return getattr(module, model_name, None)

# ---------- RÉCONCILIATION COLONNES (NOUVEAU) ----------
def _db_columns(table_name: str) -> set[str]:
    """Liste les colonnes existantes dans la table (schéma courant)."""
    with connection.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = %s
            """,
            [table_name],
        )
        return {row[0] for row in cur.fetchall()}

def _ensure_table_columns_match_model(model_class, table_name: str):
    """
    Ajoute via schema_editor.add_field() tout champ de modèle manquant en base.
    Tous nos champs générés sont nullables => safe à ADD.
    """
    if not model_class:
        return
    existing = _db_columns(table_name)
    missing = []
    with connection.schema_editor() as se:
        for field in model_class._meta.local_fields:  # pas de M2M ici
            col = field.column  # tient compte de db_column et FK "_id"
            if col and col not in existing:
                se.add_field(model_class, field)
                missing.append(col)
    if missing:
        logger.info(f"Added missing columns to {table_name}: {missing}")

# -------------------- Générateur principal --------------------
def generate_app(kobo_form_id: int):
    form = KoboForm.objects.get(pk=kobo_form_id)
    app_slug = form.slug

    # 0) mapping prêt (ou construit via sample)
    maps_qs = _ensure_maps_from_sample_if_missing(form)

    # 1) repeat prefixes: maps + sample + *_count
    explicit_repeat_prefixes: set[str] = set(
        (m["kobo_name"] or "").split("/", 1)[0]
        for m in maps_qs
        if (m["dtype"] or "").strip().lower() == "repeat"
    )
    sample = form.sample_json if isinstance(form.sample_json, dict) else None
    sample_repeat_prefixes = _repeat_prefixes_from_sample_dict(sample)
    names = [(m["kobo_name"] or "").strip() for m in maps_qs]
    count_repeat_prefixes = {n[:-6] for n in names if n.endswith("_count")}
    repeat_prefixes = explicit_repeat_prefixes | sample_repeat_prefixes | count_repeat_prefixes

    # 2) dispatcher parent vs enfants
    used_parent: set[str] = set()
    parent_fields_code: List[str] = []
    repeats_fields: DefaultDict[str, List[dict]] = defaultdict(list)

    for m in maps_qs:
        kn = (m["kobo_name"] or "").strip()
        raw_model = (m["model_field"] or "").strip()
        dt = (m["dtype"] or "string").strip().lower()

        if dt == "repeat":
            continue

        if "/" in kn:
            prefix, suffix = kn.split("/", 1)
        else:
            prefix, suffix = kn, None

        if suffix and prefix in repeat_prefixes:
            repeats_fields[prefix].append({
                "kobo_name": kn,
                "prefix": prefix,
                "suffix": suffix,
                "dtype": dt,
                "raw_model": raw_model,
                "id": m.get("id"),
            })
            continue

        # champ parent
        fname = canon_name(raw_model or kn.replace("/", "_"), used_parent)
        if fname in SYSTEM_PARENT_FIELDS:
            continue
        if raw_model and fname != raw_model and m.get("id"):
            KoboFieldMap.objects.filter(id=m["id"]).update(model_field=fname)
        used_parent.add(fname)
        field_def = TYPE_MAP.get(dt, TYPE_MAP["string"])
        parent_fields_code.append(f"    {fname} = {field_def}")

    # champs système au parent
    system_fields = [
        "    instance_id = models.CharField(max_length=128, db_index=True, blank=True, null=True)",
        "    xform_id_string = models.CharField(max_length=200, blank=True, null=True)",
        "    submission_time = models.DateTimeField(blank=True, null=True)",
        "    submitted_by = models.CharField(max_length=150, blank=True, null=True)",
        "    status = models.CharField(max_length=50, blank=True, null=True)",
        "    geojson = models.JSONField(blank=True, null=True)",
        "    raw_json = models.JSONField(blank=True, null=True)",
        "    created_at = models.DateTimeField(auto_now_add=True)",
        "    updated_at = models.DateTimeField(auto_now=True)",
    ]

    # 3) répertoires & noms
    _ensure_generated_apps_pkg()
    app_dir = Path(settings.BASE_DIR) / "generated_apps" / app_slug
    app_dir.mkdir(parents=True, exist_ok=True)
    model_name = detect_existing_model_name(app_dir) or model_name_from_slug(app_slug)

    # Génération du nom de table court
    table_name = _generate_table_name(app_slug, model_name)
    logger.info(f"Generated table name: {table_name} for model {model_name}")

    # list_display parent
    list_cols = ["id"]
    list_cols += [re.findall(r"^\s*([a-z0-9_]+)\s*=", line)[0]
                  for line in parent_fields_code[:5] if "=" in line]

    # 4) models.py — parent + enfants (si existants)
    parent_model_code = (
        "from django.db import models\n\n"
        f"class {model_name}(models.Model):\n"
        f"{('\n'.join(parent_fields_code + system_fields) if parent_fields_code else '\n'.join(system_fields))}\n\n"
        f"    class Meta:\n"
        f"        db_table = '{table_name}'\n"
        "        ordering = ('-id',)\n\n"
        "    def __str__(self):\n"
        f"        return f\"{model_name} #{{self.pk}}\"\n"
    )

    children_code: List[str] = []
    admin_inlines_code: List[str] = []
    child_class_names: List[str] = []

    for prefix, fields in repeats_fields.items():
        child_class = _generate_child_class_name(model_name, prefix)
        child_class_names.append(child_class)

        used_child: set[str] = set()
        child_lines: List[str] = [
            f"    parent = models.ForeignKey('{model_name}', on_delete=models.CASCADE, related_name='{canon_name(prefix, set())}_items')",
            "    item_index = models.IntegerField(blank=True, null=True)",
            "    raw_json = models.JSONField(blank=True, null=True)",
        ]

        for f in fields:
            raw_model = (f['raw_model'] or f['suffix']).strip()
            fname = canon_name(raw_model, used_child)
            if raw_model and fname != raw_model and f.get('id'):
                KoboFieldMap.objects.filter(id=f['id']).update(model_field=fname)
            used_child.add(fname)
            field_def = TYPE_MAP.get(f["dtype"], TYPE_MAP["string"])
            child_lines.append(f"    {fname} = {field_def}")

        child_table_name = _generate_table_name(app_slug, child_class)
        logger.info(f"Generated child table name: {child_table_name} for model {child_class}")

        code = (
            f"\n\nclass {child_class}(models.Model):\n"
            + "\n".join(child_lines)
            + "\n\n"
            "    class Meta:\n"
            f"        db_table = '{child_table_name}'\n"
            "        ordering = ('parent_id', 'item_index')\n"
            "        unique_together = (('parent', 'item_index'),)\n\n"
            "    def __str__(self):\n"
            f"        return f\"{child_class} of {{self.parent_id}}[{{self.item_index}}]\"\n"
        )
        children_code.append(code)

        admin_inlines_code.append(
            f"\nclass {child_class}Inline(admin.TabularInline):\n"
            f"    model = {child_class}\n"
            "    extra = 0\n"
        )

    (app_dir / "models.py").write_text(parent_model_code + "".join(children_code), encoding="utf-8")

    # 5) admin.py
    admin_code = (
        "from django.contrib import admin\n"
        f"from .models import {model_name}"
    )
    if child_class_names:
        admin_code += ", " + ", ".join(child_class_names)
    admin_code += "\n\n"
    if child_class_names:
        admin_code += "".join(admin_inlines_code)
    admin_code += (
        f"\n@admin.register({model_name})\n"
        "class ParentAdmin(admin.ModelAdmin):\n"
        f"    list_display = {tuple(list_cols)}\n"
    )
    if child_class_names:
        admin_code += f"    inlines = [{', '.join([f'{n}Inline' for n in child_class_names])}]\n"
    (app_dir / "admin.py").write_text(admin_code, encoding="utf-8")

    # 6) fichiers de base (apps/forms/views/urls)
    def safe_write(filename: str, content: str):
        (app_dir / filename).write_text(content, encoding="utf-8")

    (app_dir / "__init__.py").write_text("", encoding="utf-8")
    safe_write(
        "apps.py",
        f"from django.apps import AppConfig\n\n"
        f"class {camelize(app_slug)}Config(AppConfig):\n"
        f"    name = 'generated_apps.{app_slug}'\n"
        f"    verbose_name = '{app_slug}'\n"
    )
    safe_write(
        "forms.py",
        "from django import forms\n"
        f"from .models import {model_name}\n\n"
        f"class {form_class_name_for(model_name)}(forms.ModelForm):\n"
        f"    class Meta:\n"
        f"        model = {model_name}\n"
        f"        fields = '__all__'\n"
    )
    views_code = (
        "from django.contrib.auth.mixins import LoginRequiredMixin\n"
        "from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, View\n"
        "from django.urls import reverse_lazy\n"
        "from django.http import HttpResponse\n"
        f"from .models import {model_name}\n"
        f"from .forms import {form_class_name_for(model_name)}\n\n"
        f"class List(LoginRequiredMixin, ListView):\n"
        f"    model = {model_name}\n"
        f"    template_name = '{app_slug}/list.html'\n\n"
        f"class Create(LoginRequiredMixin, CreateView):\n"
        f"    model = {model_name}\n"
        f"    form_class = {form_class_name_for(model_name)}\n"
        f"    template_name = '{app_slug}/form.html'\n"
        f"    success_url = reverse_lazy('{app_slug}:list')\n\n"
        f"class Update(LoginRequiredMixin, UpdateView):\n"
        f"    model = {model_name}\n"
        f"    form_class = {form_class_name_for(model_name)}\n"
        f"    template_name = '{app_slug}/form.html'\n"
        f"    success_url = reverse_lazy('{app_slug}:list')\n\n"
        f"class Delete(LoginRequiredMixin, DeleteView):\n"
        f"    model = {model_name}\n"
        f"    success_url = reverse_lazy('{app_slug}:list')\n\n"
        "class Dashboard(LoginRequiredMixin, TemplateView):\n"
        f"    template_name = '{app_slug}/dashboard.html'\n\n"
        "class Export(LoginRequiredMixin, View):\n"
        "    def get(self, request, *args, **kwargs):\n"
        "        resp = HttpResponse('id\\n', content_type='text/csv')\n"
        f"        resp['Content-Disposition'] = 'attachment; filename=\"{app_slug}.csv\"'\n"
        "        return resp\n"
    )
    safe_write("views.py", views_code)

    urls_code = (
        "from django.urls import path\n"
        "from .views import List, Create, Update, Delete, Dashboard, Export\n\n"
        "app_name = __package__.split('.')[-1]\n\n"
        "urlpatterns = [\n"
        "    path('', List.as_view(), name='list'),\n"
        "    path('create/', Create.as_view(), name='create'),\n"
        "    path('<int:pk>/update/', Update.as_view(), name='update'),\n"
        "    path('<int:pk>/delete/', Delete.as_view(), name='delete'),\n"
        "    path('dashboard/', Dashboard.as_view(), name='dashboard'),\n"
        "    path('export/', Export.as_view(), name='export'),\n"
        "]\n"
    )
    safe_write("urls.py", urls_code)

    # 7) settings + migrations
    ensure_app_declared_in_settings(app_slug)

    migration_output = ""
    table_created = False

    try:
        # Désinstaller proprement si des migrations existent
        try:
            run_manage("migrate", app_slug, "zero", "--noinput")
            migration_output += "App uninstalled successfully\n"
        except RuntimeError as e:
            if "does not have migrations" in str(e):
                migration_output += "App had no migrations to uninstall\n"
            else:
                raise

        _reset_migrations(app_dir)
        _create_empty_migration(app_dir, app_slug)

        out1 = run_manage("makemigrations", app_slug)
        migration_output += out1

        # ✅ Migration tolérante: --fake-initial pour éviter DuplicateTable si tables déjà là
        out2 = run_manage("migrate", app_slug, "--noinput", "--fake-initial")
        migration_output += out2

        # Parent: s’assurer que la table existe, sinon création directe
        if not _table_exists(table_name):
            logger.warning(f"Table principale '{table_name}' n'existe pas, création directe")
            model_class = _load_model_class(app_slug, model_name)
            if model_class:
                _create_table_with_schema_editor(model_class)
                migration_output += f"Table '{table_name}' created directly with schema editor\n"
                table_created = True
            else:
                raise RuntimeError(f"Model class for {model_name} not found")

        # Enfants: idem
        for child_class_name in child_class_names:
            child_table_name = _generate_table_name(app_slug, child_class_name)
            if not _table_exists(child_table_name):
                logger.warning(f"Table enfant '{child_table_name}' n'existe pas, création directe")
                child_model_class = _load_model_class(app_slug, child_class_name)
                if child_model_class:
                    _create_table_with_schema_editor(child_model_class)
                    migration_output += f"Child table '{child_table_name}' created directly with schema editor\n"
                else:
                    migration_output += f"Warning: Child model class '{child_class_name}' not found\n"

        # ---------- Réconciliation colonnes manquantes ----------
        try:
            parent_cls = _load_model_class(app_slug, model_name)
            _ensure_table_columns_match_model(parent_cls, table_name)
        except Exception as e:
            logger.warning(f"Reconciliation parent failed for {table_name}: {e}")

        for child_class_name in child_class_names:
            child_table_name = _generate_table_name(app_slug, child_class_name)
            try:
                child_cls = _load_model_class(app_slug, child_class_name)
                _ensure_table_columns_match_model(child_cls, child_table_name)
            except Exception as e:
                logger.warning(f"Reconciliation child failed for {child_table_name}: {e}")

    except RuntimeError as e:
        migration_output += f"\nMigration error: {str(e)}"
        logger.error(f"Migration failed for {app_slug}: {e}")

        if not table_created and not _table_exists(table_name):
            try:
                model_class = _load_model_class(app_slug, model_name)
                if model_class:
                    _create_table_with_schema_editor(model_class)
                    migration_output += f"Table '{table_name}' created directly with schema editor after failure\n"
            except Exception as e2:
                migration_output += f"Failed to create table directly: {e2}"

        for child_class_name in child_class_names:
            child_table_name = _generate_table_name(app_slug, child_class_name)
            if not _table_exists(child_table_name):
                try:
                    child_model_class = _load_model_class(app_slug, child_class_name)
                    if child_model_class:
                        _create_table_with_schema_editor(child_model_class)
                        migration_output += f"Child table '{child_table_name}' created directly after failure\n"
                except Exception as e2:
                    migration_output += f"Failed to create child table directly: {e2}"

        # Même en cas d'erreur, tenter la réconciliation
        try:
            parent_cls = _load_model_class(app_slug, model_name)
            _ensure_table_columns_match_model(parent_cls, table_name)
        except Exception:
            pass
        for child_class_name in child_class_names:
            try:
                child_cls = _load_model_class(app_slug, child_class_name)
                child_table_name = _generate_table_name(app_slug, child_class_name)
                _ensure_table_columns_match_model(child_cls, child_table_name)
            except Exception:
                pass

    logger.info(f"App {app_slug} generated successfully")
    return app_slug, model_name, migration_output
