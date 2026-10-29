import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
def _load_env_file(filepath: Path) -> None:
    if not filepath.exists():
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

_load_env_file(BASE_DIR / ".env")

# Core App Configuration
APP_ENV = os.getenv("APP_ENV", "development").lower()
SECRET_KEY = os.getenv("APP_SECRET_KEY") or os.getenv("SECRET_KEY", "django-insecure-dev-session-key-change-in-production")
DEBUG = APP_ENV != "production"

if not DEBUG and len(SECRET_KEY) < 32:
    raise RuntimeError("APP_SECRET_KEY must be set to at least 32 characters in production.")

ALLOWED_HOSTS = ["*"]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "corsheaders",
    "rest_framework",
    # Local Apps
    "apps.core.apps.CoreConfig",
    "apps.appointments.apps.AppointmentsConfig",
    "apps.compliance.apps.ComplianceConfig",
    "apps.telemetry.apps.TelemetryConfig",
    "apps.voice_telephony.apps.VoiceTelephonyConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "voice_receptionist.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "static"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "voice_receptionist.wsgi.application"
ASGI_APPLICATION = "voice_receptionist.asgi.application"

# Database configuration: SQLite default or PostgreSQL via DATABASE_URL
DEFAULT_SQLITE_PATH = str(BASE_DIR / "data" / "voice_enterprise.sqlite3")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", DEFAULT_SQLITE_PATH)

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    try:
        import dj_database_url
        DATABASES = {"default": dj_database_url.config(default=DATABASE_URL, conn_max_age=600)}
    except ImportError:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": SQLITE_DB_PATH,
                "OPTIONS": {"timeout": 30},
            }
        }
else:
    # Ensure data folder exists
    Path(SQLITE_DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": SQLITE_DB_PATH,
            "OPTIONS": {"timeout": 30},
        }
    }

AUTH_USER_MODEL = "core.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

PUBLIC_DIR = BASE_DIR / "public"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# CORS
CORS_ALLOW_ALL_ORIGINS = True

# Session settings
SESSION_COOKIE_NAME = "ar_session"
SESSION_COOKIE_AGE = 60 * 60 * 12  # 12 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SAMESITE = "Lax"

# REST Framework settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

# Domain & Voice Credentials
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
BOOTSTRAP_ADMIN_EMAIL = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
BOOTSTRAP_ADMIN_PASSWORD = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "")
VOICE_ASSISTANT_TENANT_MAP_RAW = os.getenv("VOICE_ASSISTANT_TENANT_MAP_RAW", "{}")

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "+15550199999")
HUMAN_ESCALATION_NUMBER = os.getenv("HUMAN_ESCALATION_NUMBER", "+15550123456")
SLACK_NOTIFICATION_WEBHOOK = os.getenv("SLACK_NOTIFICATION_WEBHOOK", "")

DEFAULT_AVG_TICKET_USD = float(os.getenv("DEFAULT_AVG_TICKET_USD", "450.0"))
DEFAULT_CLOSE_RATE = float(os.getenv("DEFAULT_CLOSE_RATE", "0.35"))

