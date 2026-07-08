import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(dotenv_path=BASE_DIR / '.env')



# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/6.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "temporary-development-key"
)

DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,::1').split(',')

STATIC_ROOT = BASE_DIR / "staticfiles"


# Application definition

INSTALLED_APPS = [
    'store.apps.StoreConfig',
    'accounts.apps.AccountsConfig',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Phase 12: Middleware to forward all requests to NetWatch
    'store.middleware.NetWatchForwardingMiddleware',
    'store.middleware.SecurityHeadersMiddleware',
    'store.middleware.PerformanceTelemetryMiddleware',
]

ROOT_URLCONF = 'shopsafe.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'shopsafe.wsgi.application'


# Database
# https://docs.djangoproject.com/en/6.0/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/6.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 12,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'accounts.validators.ComplexityValidator',
    },
]

# ─── Secure Session Management ──────────────────────────────────────────────
# Protect cookies against hijacking and scripting extraction
SESSION_COOKIE_SECURE = False  # Set to True in production (requires HTTPS)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

CSRF_COOKIE_SECURE = False  # Set to True in production (requires HTTPS)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Lax'

# ─── Account Lockout and Security Limits ────────────────────────────────────
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15

# ─── Google reCAPTCHA v2 checkbox configurations ───────────────────────────
RECAPTCHA_SITE_KEY = os.getenv("RECAPTCHA_SITE_KEY", "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe")
RECAPTCHA_SCORE_THRESHOLD = 0.5

# ─── NetWatch Ingest API & Security Events Integration ──────────────────────
# The URL and key used to forward all HTTP traffic logs and security events to NetWatch.
NETWATCH_API_URL = os.getenv('NETWATCH_API_URL', 'http://127.0.0.1:8000/api/ingest/')
NETWATCH_EVENTS_API_URL = os.getenv('NETWATCH_EVENTS_API_URL', 'http://127.0.0.1:8000/api/events/')
NETWATCH_API_KEY = os.getenv('NETWATCH_API_KEY', 'nw-capstone-2026-secret-key')



# Internationalization
# https://docs.djangoproject.com/en/6.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Manila'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/6.0/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

# ─── Auth Redirects ────────────────────────────────────────────────────────
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

# ─── Unique Cookie Configurations to Prevent Session Clashes ─────────────────
SESSION_COOKIE_NAME = 'shopsafe_sessionid'
CSRF_COOKIE_NAME = 'shopsafe_csrftoken'

# ─── Email Configuration (OTP Gmail Delivery) ────────────────────────────────
# To send real emails, create a .env file in the ShopSafe root directory with:
#   EMAIL_HOST_USER=your-email@gmail.com
#   EMAIL_HOST_PASSWORD=your-gmail-app-password
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = 'smtp.gmail.com'
    EMAIL_PORT = 587
    EMAIL_USE_TLS = True
    DEFAULT_FROM_EMAIL = f'ShopSafe <{EMAIL_HOST_USER}>'
else:
    EMAIL_BACKEND = 'django.core.mail.backends.filebased.EmailBackend'
    EMAIL_FILE_PATH = os.path.join(BASE_DIR, 'sent_emails')


