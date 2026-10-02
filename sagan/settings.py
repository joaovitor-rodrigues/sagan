import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Vercel define VERCEL=1 no build e em runtime.
ON_VERCEL = bool(os.environ.get("VERCEL"))


def _env_bool(name, default):
    return os.environ.get(name, str(default)).lower() in ("1", "true", "yes")


def _env_list(name, default=""):
    return [v.strip() for v in os.environ.get(name, default).split(",") if v.strip()]


# Configuração via variáveis de ambiente (veja .env.example).
# Os valores padrão servem apenas para desenvolvimento local.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-dev-only-nao-use-em-producao",
)

DEBUG = _env_bool("DJANGO_DEBUG", not ON_VERCEL)

ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

if ON_VERCEL:
    ALLOWED_HOSTS += [".vercel.app"]
    CSRF_TRUSTED_ORIGINS += ["https://*.vercel.app"]
    # A Vercel termina o TLS no proxy e repassa o protocolo original neste header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Só /tmp é gravável nas funções: caches do astropy/lightkurve/matplotlib vão para lá.
    _tmp = Path("/tmp/sagan")
    for sub in ("cache/astropy", "cache/lightkurve", "config/astropy", "config/lightkurve", "mpl", "downloads"):
        (_tmp / sub).mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("XDG_CACHE_HOME", str(_tmp / "cache"))
    os.environ.setdefault("XDG_CONFIG_HOME", str(_tmp / "config"))
    os.environ.setdefault("MPLCONFIGDIR", str(_tmp / "mpl"))
    os.environ.setdefault("SAGAN_CACHE_DIR", str(_tmp / "downloads"))

# O app não usa banco de dados: o catálogo vem do ExoFOP (cache em memória)
# e o estado da análise fica no navegador. Por isso não há admin, auth nem sessões.
INSTALLED_APPS = [
    'django.contrib.contenttypes',
    'django.contrib.staticfiles',
    'app',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'sagan.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
            ],
        },
    },
]

WSGI_APPLICATION = 'sagan.wsgi.application'

DATABASES = {}

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
# Na Vercel o collectstatic roda automaticamente no build e os arquivos
# são servidos pela CDN a partir daqui.
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
