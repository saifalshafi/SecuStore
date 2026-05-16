"""
Django settings for project1 — Secure File Storage System (Production Ready)
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ─────────────────────────────────────────────
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'change-this-in-production')

MASTER_ENCRYPTION_KEY = os.environ.get(
    'MASTER_ENCRYPTION_KEY',
    'change-this-too'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() == 'true'

# Render / Production hosts
ALLOWED_HOSTS = ['*']

# ── Apps ────────────────────────────────────────────────
INSTALLED_APPS = [
    'unfold',
    'auditlog',
    'axes',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'django_password_validators',

    'pages.apps.PagesConfig',
    'Accounts.apps.AccountsConfig',
    'files.apps.FilesConfig',
    'monitoring.apps.MonitoringConfig',
]

# ── Middleware ──────────────────────────────────────────
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',

    # WhiteNoise (IMPORTANT for Render)
    'whitenoise.middleware.WhiteNoiseMiddleware',

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',

    'axes.middleware.AxesMiddleware',
    'auditlog.middleware.AuditlogMiddleware',
    'project1.middleware.HideAdminMiddleware',
]

ROOT_URLCONF = 'project1.urls'

# ── Templates ───────────────────────────────────────────
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'project1.context_processors.user_file_stats',
            ],
        },
    },
]

WSGI_APPLICATION = 'project1.wsgi.application'

# ── Database (Render لاحقاً PostgreSQL) ────────────────
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('DB_NAME', 'secstore'),
        'USER': os.environ.get('DB_USER', 'root'),
        'PASSWORD': os.environ.get('DB_PASSWORD', ''),
        'HOST': os.environ.get('DB_HOST', 'localhost'),
        'PORT': os.environ.get('DB_PORT', '3306'),
    }
}

# ── Password validation ────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': (
            'django_password_validators.password_character_requirements'
            '.password_validation.PasswordCharacterValidator'
        ),
        'OPTIONS': {
            'min_length_digit': 4,
            'min_length_alpha': 4,
            'min_length_special': 1,
            'min_length_lower': 1,
            'min_length_upper': 1,
            'special_characters': "~!@#$%^&*()+{}:;'[]",
        },
    },
]

# ── International ──────────────────────────────────────
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# ── Static & Media ──────────────────────────────────────
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

STATICFILES_DIRS = [os.path.join(BASE_DIR, 'project1/static')]

# WhiteNoise storage (IMPORTANT)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── Email (use ENV in production) ──────────────────────
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 465
EMAIL_USE_TLS = False
EMAIL_USE_SSL = True

EMAIL_HOST_USER = os.environ.get('saefalshafi@gmail.com')
EMAIL_HOST_PASSWORD = os.environ.get('jspm zkry zrbx iude')

# ── Sessions ───────────────────────────────────────────
SESSION_COOKIE_AGE = 600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

LOGIN_REDIRECT_URL = 'intro'
LOGIN_URL = 'login'
LOGOUT_REDIRECT_URL = '/Accounts/login'

# ── Security headers ───────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

# ── Password Hashing ───────────────────────────────────
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]