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

# 1. On autorise toujours le local
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# 2. On ajoute dynamiquement l'URL Render (Variable automatique de Render)
# Cette variable est TOUJOURS présente sur Render, pas besoin de la créer
render_external_hostname = os.environ.get('RENDER_EXTERNAL_HOSTNAME')
if render_external_hostname:
    ALLOWED_HOSTS.append(render_external_hostname)

# 3. On ajoute manuellement votre domaine spécifique par sécurité
ALLOWED_HOSTS.append('mbongi-agents.onrender.com')

# 4. Optionnel : On ajoute la variable d'environnement personnalisée si elle existe
env_hosts = os.environ.get("ALLOWED_HOSTS")
if env_hosts:
    ALLOWED_HOSTS.extend([host.strip() for host in env_hosts.split(",")])

# Nettoyage final pour éviter les doublons
ALLOWED_HOSTS = list(set(ALLOWED_HOSTS))



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
