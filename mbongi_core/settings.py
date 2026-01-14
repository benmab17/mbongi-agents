from pathlib import Path
import os

# =========================
# BASE
# =========================
BASE_DIR = Path(__file__).resolve().parent.parent


# =========================
# SÉCURITÉ / DEBUG
# =========================
SECRET_KEY = 'django-insecure-07(pa2udqy5o@94bi8foo&*kg!%ls+*%5pxq^h1v4ryap)wr^r'

DEBUG = True

# --- CONFIGURATION DES CHEMINS ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- SÉCURITÉ / DEBUG ---
# En production sur Render, on récupère la clé depuis une variable d'environnement
# Si elle n'existe pas, on utilise une clé de secours (uniquement pour le local)
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-07(pa2udqy5o@94bi8foo&*kg!%ls+*%5pxq^h1v4ryap)wr^r')

# Passer à False en production pour ne plus afficher les erreurs détaillées
DEBUG = os.environ.get('DEBUG', 'True') == 'True'

# --- Section ALLOWED_HOSTS ---
# 1. Base par défaut (Local + Domaine connu)
ALLOWED_HOSTS = ['127.0.0.1', 'localhost', 'mbongi-agents.onrender.com']

# 2. Récupération automatique du hostname Render (injecté par Render au déploiement)
render_external_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_external_hostname:
    ALLOWED_HOSTS.append(render_external_hostname)

# 3. Ajout via variable d'environnement personnalisée (si besoin)
env_hosts = os.environ.get("ALLOWED_HOSTS")
if env_hosts:
    ALLOWED_HOSTS.extend([host.strip() for host in env_hosts.split(",")])

# 4. Nettoyage des doublons
ALLOWED_HOSTS = list(set(ALLOWED_HOSTS))

# --- Section SÉCURITÉ HTTPS & CSRF ---

# Indispensable pour que Django accepte les connexions HTTPS derrière le proxy de Render
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Obligatoire pour Django 6.x pour pouvoir se connecter à l'admin et soumettre des formulaires
CSRF_TRUSTED_ORIGINS = [
    "https://mbongi-agents.onrender.com",
]

# Ajout dynamique du domaine Render actuel aux origines CSRF de confiance
if render_external_hostname:
    CSRF_TRUSTED_ORIGINS.append(f"https://{render_external_hostname}")

# --- CONFIGURATION DES FICHIERS STATIQUES (Recommandé pour Render) ---
STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Si vous installez 'whitenoise', ajoutez-le dans vos MIDDLEWARE (juste après SecurityMiddleware)


# =========================
# APPLICATIONS
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


# =========================
# MIDDLEWARE
# =========================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
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
