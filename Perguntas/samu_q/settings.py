import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'dev-insecure-secret')
DEBUG = os.getenv('DJANGO_DEBUG', 'True') == 'True'
ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if h.strip()]

# CSRF trusted origins (inclui esquema). Ex: "http://localhost,http://127.0.0.1,http://3.150.194.173"
_csrf_trusted = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if _csrf_trusted:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in _csrf_trusted.split(',') if o.strip()]

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
# Ao deslogar queremos voltar para a home pública
LOGOUT_REDIRECT_URL = os.getenv('LOGOUT_REDIRECT_URL', '/')

LOGIN_URL = os.getenv('LOGIN_URL', '/login/')

# Segurança adicional quando HTTPS/produção
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    # HSTS (cuidado em ambiente de staging). Ajuste o tempo após validar HTTPS.
    SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '63072000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = False  # Normalmente False; manter explícito
    # Ajuste se for necessário trust adicional de proxy
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
