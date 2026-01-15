from pathlib import Path
import os
import dj_database_url


# =========================
# BASE
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent


# =========================
# SÉCURITÉ / DEBUG
# =========================
SECRET_KEY = 'django-insecure-07(pa2udqy5o@94bi8foo&*kg!%ls+*%5pxq^h1v4ryap)wr^r'

DEBUG = True

# Assurez-vous que BASE_DIR pointe vers la racine du projet
BASE_DIR = Path(__file__).resolve().parent.parent

# --- CONFIGURATION STATIQUE POUR RAILWAY ---
STATIC_URL = 'static/'

# Indique à Django où mettre les fichiers rassemblés pour la production
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Indique à Django où chercher vos fichiers CSS/JS en local
# Assurez-vous de CRÉER un dossier nommé 'static' à côté de manage.py
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# Indispensable pour que Railway puisse lire et servir ces fichiers
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
# =========================

INSTALLED_APPS = [
    # Django core
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Apps projet
    'accounts',
    'agents',
]

CSRF_TRUSTED_ORIGINS = [
    "https://mbongi-agents-production.up.railway.app",
    "https://*.up.railway.app",
]


# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
]


# =========================
# URLS / WSGI
# =========================
ROOT_URLCONF = 'mbongi_core.urls'

WSGI_APPLICATION = 'mbongi_core.wsgi.application'


# =========================
# TEMPLATES
# =========================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],  # on utilise APP_DIRS
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                "accounts.context_processors.nav_context",
                "agents.context_processors.current_context",

            ],
        },
    },
]


# =========================
# DATABASE
# =========================
# 1. On récupère la configuration depuis DATABASE_URL sans valeur par défaut
db_config = dj_database_url.config(conn_max_age=600)

if db_config:
    # Si on est sur Railway (DATABASE_URL existe)
    DATABASES = {"default": db_config}
    DATABASES["default"]["OPTIONS"] = {"sslmode": "require"}
else:
    # Si on est en local (DATABASE_URL absente)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# =========================
# AUTH / LOGIN
# =========================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"


# =========================
# INTERNATIONALISATION
# =========================
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = 'UTC'

USE_I18N = True
USE_TZ = True


# =========================
# STATIC FILES
# =========================
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",
]


# =========================
# MEDIA (UPLOAD PHOTOS)
# =========================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# =========================
# DEFAULT PRIMARY KEY
# =========================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
