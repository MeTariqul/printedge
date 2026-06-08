"""
Print-Edge Django Settings - Production Ready
"""
import os
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-this-in-production')
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

def normalize_host(value):
    if not value:
        return ''
    host = value.strip()
    if '://' in host:
        host = urlparse(host).netloc or urlparse(host).path
    host = host.split('/', 1)[0].strip()
    if host.startswith('.'):
        return host
    if ':' in host and not host.startswith('['):
        host = host.split(':', 1)[0]
    return host


def origin_from_host(value):
    host = normalize_host(value)
    if not host or host in {'localhost', '127.0.0.1', 'testserver'}:
        return ''
    scheme = 'http' if host.startswith('localhost') or host.startswith('127.0.0.1') else 'https'
    return f'{scheme}://{host}'


default_allowed_hosts = {'localhost', '127.0.0.1', 'testserver'}
configured_allowed_hosts = {
    normalize_host(host)
    for host in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver').split(',')
    if normalize_host(host)
}

vercel_host_candidates = {
    os.environ.get('VERCEL_URL', ''),
    os.environ.get('VERCEL_PROJECT_PRODUCTION_URL', ''),
    os.environ.get('VERCEL_BRANCH_URL', ''),
    os.environ.get('SITE_DOMAIN', ''),
}

resolved_vercel_hosts = {normalize_host(host) for host in vercel_host_candidates if normalize_host(host)}
ALLOWED_HOSTS = sorted(default_allowed_hosts | configured_allowed_hosts | resolved_vercel_hosts)

csrf_trusted_origins = {
    'https://*.vercel.app',
    'https://*.vercel.com',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
}
csrf_trusted_origins.update(
    origin for origin in (origin_from_host(host) for host in resolved_vercel_hosts) if origin
)
CSRF_TRUSTED_ORIGINS = sorted(csrf_trusted_origins)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'core',
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
    'core.middleware.SecurityHeadersMiddleware',
    'core.middleware.AuditLogMiddleware',
]

ROOT_URLCONF = 'print_edge.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.site_settings',
                'core.context_processors.supabase_config',
            ],
        },
    },
]

WSGI_APPLICATION = 'print_edge.wsgi.application'

import dj_database_url
import os

DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL', 'postgresql://postgres.grcgetateedtitnlpogb:PrintEaseDB2026@aws-1-ap-southeast-2.pooler.supabase.com:6543/postgres'),
        conn_max_age=300,
    )
}

AUTH_USER_MODEL = 'core.User'
LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/user/dashboard/'
LOGOUT_REDIRECT_URL = '/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
AUTHENTICATION_BACKENDS = [
    'core.auth_backends.EmailBackend',
]

LANGUAGE_CODE = 'en'
TIME_ZONE = 'Asia/Dhaka'
USE_I18N = False
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
        'OPTIONS': {'location': MEDIA_ROOT, 'base_url': MEDIA_URL},
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Cloud Storage (Supabase via S3-compatible API) - used only when Supabase credentials are provided.
# In local development with empty Supabase vars, files will be stored on the local MEDIA_ROOT via the
# FileSystemStorage backend above. When deployed (e.g., Vercel), these env vars will be present and
# the project will switch to Supabase Storage automatically.
def _supabase_s3_endpoint():
    explicit = os.environ.get('AWS_S3_ENDPOINT_URL', '').strip()
    if explicit:
        return explicit.rstrip('/')
    base = os.environ.get('SUPABASE_URL', '').rstrip('/')
    if not base:
        return ''
    if '.supabase.co' in base:
        host = base.split('//', 1)[-1]
        project_ref = host.split('.')[0]
        return f'https://{project_ref}.storage.supabase.co/storage/v1/s3'
    return ''


_service_role = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
_supabase_bucket = os.environ.get('SUPABASE_STORAGE_BUCKET', 'order-files')
_s3_endpoint = _supabase_s3_endpoint()

_aws_key = os.environ.get('SUPABASE_S3_ACCESS_KEY_ID', '') or _service_role
_aws_secret = os.environ.get('SUPABASE_S3_SECRET_ACCESS_KEY', '') or _service_role

if _aws_key and _aws_secret and _supabase_bucket and _s3_endpoint:
    supabase_url = _s3_endpoint.rstrip('/')

    AWS_S3_ENDPOINT_URL    = supabase_url
    AWS_ACCESS_KEY_ID      = _aws_key
    AWS_SECRET_ACCESS_KEY  = _aws_secret
    AWS_STORAGE_BUCKET_NAME = _supabase_bucket
    AWS_S3_REGION_NAME     = os.environ.get('AWS_S3_REGION_NAME', 'auto')
    AWS_S3_SIGNATURE_VERSION = os.environ.get('AWS_S3_SIGNATURE_VERSION', 's3v4')
    AWS_S3_ADDRESSING_STYLE  = os.environ.get('AWS_S3_ADDRESSING_STYLE', 'path')

    MEDIA_URL = f"{supabase_url}/{_supabase_bucket}/"
    STORAGES['default'] = {
        'BACKEND': 'core.supabase_s3_storage.SupabaseS3Storage',
        'OPTIONS': {
            'bucket_name':               _supabase_bucket,
            'endpoint_url':              supabase_url,
            'region_name':               AWS_S3_REGION_NAME,
            'access_key':                _aws_key,
            'secret_key':                _aws_secret,
            'file_overwrite':            False,
            'querystring_auth':          False,
            'default_acl':               'private',
            'querystring_expire':        3600,
            'signature_version':         AWS_S3_SIGNATURE_VERSION,
            'addressing_style':          AWS_S3_ADDRESSING_STYLE,
            'location':                  '',
            'object_parameters':         {'CacheControl': 'max-age=86400'},
        },
    }

CRON_SECRET = os.environ.get('CRON_SECRET', '')

# Rate limiting (auth)
AUTH_RATE_LIMIT_ATTEMPTS = int(os.environ.get('AUTH_RATE_LIMIT_ATTEMPTS', '5'))
AUTH_RATE_LIMIT_WINDOW = int(os.environ.get('AUTH_RATE_LIMIT_WINDOW', '300'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# File upload limits
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800

# Sessions
SESSION_COOKIE_AGE = 1296000  # 15 days timeout
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_SSL_REDIRECT = False  # Vercel handles SSL
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'

if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Email (Brevo API)
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '')
EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'print-edge@outlook.com')

# Business Config (override via env)
BUSINESS_NAME = os.environ.get('BUSINESS_NAME', 'Print-Edge')
BUSINESS_PHONE = os.environ.get('BUSINESS_PHONE', '+8801700000000')
BUSINESS_EMAIL = os.environ.get('BUSINESS_EMAIL', 'gbtarif37@gmail.com')
BUSINESS_ADDRESS = os.environ.get(
    'BUSINESS_ADDRESS',
    'Default delivery location: Gono Bishwabidyalay (convenience point only). Not affiliated with Gono Bishwabidyalay.',
)
BUSINESS_HOURS = os.environ.get('BUSINESS_HOURS', 'Sun-Thu 9:00 AM – 5:00 PM')
BUSINESS_BKASH = os.environ.get('BUSINESS_BKASH', '')
BUSINESS_NAGAD = os.environ.get('BUSINESS_NAGAD', '')
BUSINESS_ROCKET = os.environ.get('BUSINESS_ROCKET', '')
