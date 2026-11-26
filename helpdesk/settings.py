"""
Django settings for the Mafori IT Helpdesk.

Secrets and machine-specific values come from environment variables.
Locally they're read from a .env file in the repo root (never committed);
copy .env.example to .env and fill it in. On the live host they're set in
the host's dashboard.
"""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def env(name, default=None, required=False):
    value = os.environ.get(name, default)
    if required and not value:
        raise ImproperlyConfigured(f"{name} is not set. Copy .env.example to .env and fill it in.")
    return value


def env_bool(name, default=False):
    return env(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


# ----------------------------------------------------------------------------
# Core
# ----------------------------------------------------------------------------

SECRET_KEY = env("DJANGO_SECRET_KEY", required=True)

# Off unless .env says otherwise. Never True on the live site.
DEBUG = env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = [h.strip() for h in env("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Our apps
    "accounts",
    "tickets",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Jack: everything needs a login, and anyone still on a temporary password
    # is sent to "change password" (Milestone 1). Order matters: these must
    # come after AuthenticationMiddleware.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
    "accounts.middleware.NoCacheMiddleware",
]

ROOT_URLCONF = "helpdesk.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "helpdesk.wsgi.application"

# ----------------------------------------------------------------------------
# Database (Dan) - PostgreSQL only
# ----------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", "mafori_helpdesk"),
        "USER": env("DB_USER", "helpdesk_app"),
        "PASSWORD": env("DB_PASSWORD", required=True),
        "HOST": env("DB_HOST", "localhost"),
        "PORT": env("DB_PORT", "5432"),
        # Reuse connections for 60 seconds instead of opening one per request
        "CONN_MAX_AGE": 60,
        # Check a reused connection still works before using it
        "CONN_HEALTH_CHECKS": True,
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ----------------------------------------------------------------------------
# Users and passwords
# ----------------------------------------------------------------------------

AUTH_USER_MODEL = "accounts.User"

# Our own login check with the 5-failed-attempts lockout. It is the ONLY
# backend on purpose: if Django's ModelBackend were listed too, /admin/login/
# would have no lockout.
AUTHENTICATION_BACKENDS = ["accounts.backends.LockoutBackend"]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home"  # a temporary page until the dashboard exists
LOGOUT_REDIRECT_URL = "accounts:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ----------------------------------------------------------------------------
# Sessions and cookies (Jack)
# ----------------------------------------------------------------------------

# A session ends after 30 minutes without activity.
SESSION_COOKIE_AGE = 30 * 60
SESSION_SAVE_EVERY_REQUEST = True  # each request pushes the 30 minutes forward
SESSION_COOKIE_HTTPONLY = True  # JavaScript can't read the session cookie
# HTTPS-only cookies on the live site (DEBUG is False there)
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

# ----------------------------------------------------------------------------
# Language and time
# ----------------------------------------------------------------------------

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Africa/Johannesburg"
USE_I18N = True
USE_TZ = True

# ----------------------------------------------------------------------------
# Static files (Sifiso's CSS and images)
# ----------------------------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
