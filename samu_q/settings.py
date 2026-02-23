import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
# Carrega primeiro .env (desenvolvimento) e depois .env.prod se existir, sem falhar se ausente.
load_dotenv(BASE_DIR / '.env')
prod_env_path = BASE_DIR / '.env.prod'
if prod_env_path.exists():
    load_dotenv(prod_env_path)

# SECRET_KEY: prioridade para DJANGO_SECRET_KEY, depois SECRET_KEY (usado em .env.prod), fallback inseguro.
SECRET_KEY = (
    os.getenv('DJANGO_SECRET_KEY')
    or os.getenv('SECRET_KEY')
    or 'dev-insecure-secret'
)

# DEBUG: aceita DJANGO_DEBUG ou DEBUG. Default False em produção se nenhuma variável for fornecida.
_debug_raw = os.getenv('DJANGO_DEBUG') or os.getenv('DEBUG', 'False')
DEBUG = _debug_raw.lower() in ('1', 'true', 'yes', 'on')
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if h.strip()]

# CSRF trusted origins (inclui esquema). Ex: "http://localhost,http://127.0.0.1,http://3.150.194.173"
_csrf_trusted = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if _csrf_trusted:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_trusted.split(',') if o.strip()]

# Modo simplificado: em ambiente sem domínio/HTTPS (DEBUG ou AUTO_CSRF_DEV=1),
# gerar automaticamente origens http:// para cada host explícito (evita 403 em admin/login via IP).
if (os.getenv('AUTO_CSRF_DEV', '1') in ('1','true','yes','on')):
    auto_origins = []
    for host in ALLOWED_HOSTS:
        if host == '*' or host.startswith('http://') or host.startswith('https://'):
            continue
        auto_origins.append(f"http://{host}")
    if auto_origins:
        # Mescla com existentes (se já definidos manualmente)
        if 'CSRF_TRUSTED_ORIGINS' in globals():
            # Evitar duplicados
            existing = set(CSRF_TRUSTED_ORIGINS)
            for o in auto_origins:
                if o not in existing:
                    CSRF_TRUSTED_ORIGINS.append(o)
        else:
            CSRF_TRUSTED_ORIGINS = auto_origins  # type: ignore

# Suporte a proxy (Nginx) - quando for habilitar HTTPS atrás de proxy, adicione X-Forwarded-Proto
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',
    'questions',
    'faq',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'samu_q.urls'

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
                'samu_q.context_processors.build_metadata',
            ],
        },
    },
]

WSGI_APPLICATION = 'samu_q.wsgi.application'

# Database
# Configurável por variáveis de ambiente, padrão MariaDB/MySQL
# Para desenvolvimento local sem MariaDB, defina DB_ENGINE=sqlite
# Para testes locais/CI podemos definir DB_ENGINE=sqlite para evitar necessidade de MariaDB.
# Default continua 'mysql' em produção. Em workflows configuraremos DB_ENGINE=sqlite.
DB_ENGINE = os.getenv('DB_ENGINE', os.getenv('CI_DB_ENGINE', 'mysql')).lower()

if DB_ENGINE == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.getenv('DB_NAME', 'samu_q'),
            'USER': os.getenv('DB_USER', 'samu_q'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', '127.0.0.1'),
            'PORT': int(os.getenv('DB_PORT', '3306')),
            'OPTIONS': {
                # Garante compatibilidade com MariaDB e suporte completo a emojis
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
            'TEST': {
                # Permite usar um banco de teste dedicado, evitando tentar criar/dropar o principal.
                'NAME': os.getenv('DB_TEST_NAME', os.getenv('DB_NAME', 'samu_q') + '_test')
            },
            # Mantém conexões reutilizáveis (ajuda em produção)
            'CONN_MAX_AGE': int(os.getenv('DB_CONN_MAX_AGE', '60')),
            # Usa transações por request para consistência
            'ATOMIC_REQUESTS': os.getenv('DB_ATOMIC_REQUESTS', 'True') == 'True',
        }
    }

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Bahia'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
LOGIN_REDIRECT_URL = os.getenv('LOGIN_REDIRECT_URL', '/inbox/')
# Ao deslogar queremos voltar para a tela de login
LOGOUT_REDIRECT_URL = os.getenv('LOGOUT_REDIRECT_URL', '/login/')

LOGIN_URL = os.getenv('LOGIN_URL', '/login/')

# Metadata de build (injetada via Docker build args ou variáveis runtime)
BUILD_SHA = os.getenv('BUILD_SHA', 'dev-local')
BUILD_DATE = os.getenv('BUILD_DATE', 'unknown')
APP_VERSION = os.getenv('APP_VERSION', 'dev')

# Open Graph / Facebook (para o debugger/scraper)
FB_APP_ID = os.getenv('FB_APP_ID', '').strip()

# Telegram (digest de checklists)
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
_tg_ids = os.getenv('TELEGRAM_CHAT_IDS', os.getenv('TELEGRAM_CHAT_ID', '')).strip()
TELEGRAM_CHAT_IDS = [s.strip() for s in _tg_ids.split(',') if s.strip()]

# Segurança / endurecimento condicional.
# Regras:
# - Só marca cookies como secure se realmente for forçado redirect HTTPS ou variável explícita SECURE_FORCE_COOKIES=1.
# - Mantém flags de proteção (XSS, nosniff) mesmo em dev se quiser ativar com SECURE_HARDEN_DEV=1.
def _env_flag(name, default='False'):
    return (os.getenv(name, default).lower() in ('1','true','yes','on'))

SECURE_SSL_REDIRECT = _env_flag('SECURE_SSL_REDIRECT')
SECURE_FORCE_COOKIES = _env_flag('SECURE_FORCE_COOKIES')
SECURE_HARDEN_DEV = _env_flag('SECURE_HARDEN_DEV')

# Respeita valores explícitos dos cookies se fornecidos; caso contrário calcula.
_session_cookie_secure_env = os.getenv('SESSION_COOKIE_SECURE')
_csrf_cookie_secure_env = os.getenv('CSRF_COOKIE_SECURE')

if _session_cookie_secure_env is not None:
    SESSION_COOKIE_SECURE = _session_cookie_secure_env.lower() in ('1','true','yes','on')
else:
    SESSION_COOKIE_SECURE = (SECURE_SSL_REDIRECT or SECURE_FORCE_COOKIES)

if _csrf_cookie_secure_env is not None:
    CSRF_COOKIE_SECURE = _csrf_cookie_secure_env.lower() in ('1','true','yes','on')
else:
    CSRF_COOKIE_SECURE = (SECURE_SSL_REDIRECT or SECURE_FORCE_COOKIES)

if (not DEBUG) or SECURE_HARDEN_DEV:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False  # Normalmente False

if SECURE_SSL_REDIRECT:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # Ativa HSTS apenas se realmente for redirect SSL (evitar travar ambiente HTTP simples)
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '63072000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
