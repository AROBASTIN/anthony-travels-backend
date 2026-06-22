"""
Django settings for travel_backend project.
Credentials are loaded from backend/.env — never hardcoded here.
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables from .env file (only present locally; Vercel uses env vars)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# ============================================================
# Core Security Settings — loaded from .env / Vercel env vars
# ============================================================
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'fallback-dev-key-change-in-production')

# DEBUG: False in production (Vercel sets DJANGO_DEBUG=False)
_debug_env = os.getenv('DJANGO_DEBUG', 'True')
DEBUG = _debug_env.lower() in ('true', '1', 'yes')

# ============================================================
# ALLOWED HOSTS
# Start with env-var list, then always add Vercel domains.
# ============================================================
_env_hosts = os.getenv('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [h.strip() for h in _env_hosts.split(',') if h.strip()]

# Always allow the Vercel deployment domain and localhost
VERCEL_HOSTS = [
    'anthony-travels-backend.vercel.app',
    '.vercel.app',           # any *.vercel.app preview URL
    'localhost',
    '127.0.0.1',
]
for host in VERCEL_HOSTS:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

# ============================================================
# MongoDB Atlas Configuration — loaded from .env / Vercel env vars
# ============================================================
MONGODB_URI = os.getenv('MONGODB_URI', '')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'anthony_travels')

# JWT
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'fallback-jwt-secret')

# ============================================================
# Application Definition
# ============================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'rest_framework',
    'api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',   # serves static files on Vercel
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'travel_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'travel_backend.wsgi.application'

# ============================================================
# Database
# On Vercel there is no persistent filesystem for SQLite.
# Django auth/session tables are not used (JWT-only auth),
# so we use a lightweight in-memory SQLite that won't crash.
# ============================================================
if os.getenv('VERCEL'):
    # Vercel serverless: use in-memory SQLite (no disk writes needed)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': '/tmp/db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# ============================================================
# Password Validation
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================================
# Internationalisation
# ============================================================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ============================================================
# Static Files & Media Uploads
# WhiteNoise serves static files efficiently on Vercel.
# ============================================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================================
# CORS — allow Angular dev server + production frontend
# ============================================================
CORS_ALLOW_ALL_ORIGINS = True

# For tighter production security (optional), replace with:
# CORS_ALLOWED_ORIGINS = [
#     'https://your-frontend.vercel.app',
#     'http://localhost:4200',
# ]

# ============================================================
# Django REST Framework
# ============================================================
REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

# ============================================================
# Security hardening for production (DEBUG=False)
# ============================================================
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = False   # Vercel handles HTTPS termination
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
