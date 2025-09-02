"""
Django settings for AHIS001 project.
"""

from pathlib import Path
import os

# ============
# Chemins
# ============
BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = BASE_DIR / "templates"

# ============
# .env
# ============
try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except Exception:
    # On continue même si python-dotenv n'est pas installé
    pass

def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}

def env_list(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]

# ============
# Sécurité & debug
# ============
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-unsafe")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

# ============
# Apps
# ============
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django_extensions",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.postgres",

    # 3rd-party
    "rest_framework",
    "django_filters",
    "multiselectfield",
    "crispy_forms",
    "crispy_bootstrap4",
    "simple_history",

    # Apps projet
    "Region",
    "Commune",
    "Departement",
    "Maladie",
    "Espece",
    "Effectif",
    "Année",
    "Pays",
    "Laboratoire",
    "TypeTestLabo",
    "Foyer",
    "Partenaire",
    "DeplacementAnimaux",
    "Infrastructure",
    "Document",
    "Structure",
    "Personnel",
    "Campagne",
    "data_initialization",
    "userProfile",
    "produit",
    "gestion_resources",
    "gestion_absences",
    "gestion_documents",
    "seroPPR",
    "actes_admin",
    "localisation_api",
    "sante_publique",
    "integration_kobo",
    "inspection_medicaments",
    "aibd",
    "visa_importation",
    "materiel",
    "alerts",
    "kobo_integration",
    "generated_apps",   # agrégateur
    "core_menu",
    "parametre",
    "lims",

    # Générées automatiquement
    "generated_apps.vaccination_sn",
    "generated_apps.objectif_sn",
    "generated_apps.surveillance_sn",
]

# ============
# Middleware
# ============
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "data_initialization.middleware.CurrentUserMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

# ============
# Templates
# ============
ROOT_URLCONF = "AHIS001.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATES_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core_menu.context_processors.menu",
            ],
        },
    },
]

WSGI_APPLICATION = "AHIS001.wsgi.application"

# ============
# Base de données
# ============
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "AHIS_DB"),
        "USER": os.getenv("DB_USER", "postgres"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5433"),
    }
}

# ============
# Auth / sessions
# ============
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/"

SESSION_COOKIE_AGE = int(os.getenv("SESSION_COOKIE_AGE", str(60 * 60 * 24 * 14)))  # 2 semaines
SESSION_EXPIRE_AT_BROWSER_CLOSE = env_bool("SESSION_EXPIRE_AT_BROWSER_CLOSE", False)
SESSION_SAVE_EVERY_REQUEST = env_bool("SESSION_SAVE_EVERY_REQUEST", True)

# ============
# Internationalisation
# ============
LANGUAGE_CODE = "fr"
TIME_ZONE = os.getenv("TIME_ZONE", "UTC")
USE_I18N = True
USE_TZ = True
DATE_INPUT_FORMATS = ["%d/%m/%Y"]

# ============
# Fichiers statiques & médias
# ============
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ============
# REST Framework
# ============
REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": int(os.getenv("DRF_PAGE_SIZE", "20")),
}

# ============
# CRISPY
# ============
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap4"
CRISPY_TEMPLATE_PACK = "bootstrap4"

# ============
# Email
# ============
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "ssl0.ovh.net")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", True)
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)  # à True si STARTTLS
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)

# ============
# Kobo (intégration)
# ============
KOBOTOOLBOX_BASE_URL = os.getenv("KOBOTOOLBOX_BASE_URL", "https://form.santeanimalechad.org")
KOBOTOOLBOX_TOKEN = os.getenv("KOBOTOOLBOX_TOKEN", "")
KOBOTOOLBOX_VERIFY_SSL = env_bool("KOBOTOOLBOX_VERIFY_SSL", False)
KOBOTOOLBOX_PAGE_SIZE = int(os.getenv("KOBOTOOLBOX_PAGE_SIZE", "500"))
KOBOTOOLBOX_USERNAME = os.getenv("KOBOTOOLBOX_USERNAME", "super_admin")
KOBOTOOLBOX_PASSWORD = os.getenv("KOBOTOOLBOX_PASSWORD", "")
DYNAMIC_APPS_DIR = BASE_DIR / "kobo_dynamic_apps"

# ============
# Celery
# ============
from celery.schedules import crontab

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", True)  # True en DEV si pas de worker

CELERY_BEAT_SCHEDULE = {
    "sync-kobo-every-30min": {
        "task": "kobo_integration.tasks.sync_all_kobo_data_task",
        "schedule": crontab(minute="*/30"),
        "kwargs": {"use_since": True, "overlap_minutes": 5, "limit": None},
    },
}

# ============
# Alertes CAMVAC
# ============
CAMVAC_ALERT_RECIPIENTS = env_list("CAMVAC_ALERT_RECIPIENTS", "g.kailou@woah.org")
CAMVAC_ALERT_THRESHOLDS = {
    "real": int(os.getenv("CAMVAC_THR_REAL", "40")),
    "couv": int(os.getenv("CAMVAC_THR_COUV", "50")),
    "app":  int(os.getenv("CAMVAC_THR_APP", "60")),
}

# ============
# AHIS (optionnel)
# ============
AHIS_RESULTS_ENDPOINT = os.getenv("AHIS_RESULTS_ENDPOINT")  # None par défaut
AHIS_API_TOKEN = os.getenv("AHIS_API_TOKEN")  # None par défaut
DEFAULT_FROM_NAME = "Notification AHIS"
