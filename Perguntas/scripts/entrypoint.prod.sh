#!/usr/bin/env sh
set -e

echo "[entrypoint] Iniciando container produção... (uid=$(id -u))"

if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
  export DJANGO_SETTINGS_MODULE=samu_q.settings
fi

# Espera pelo banco se for MySQL/MariaDB (porta padrão 3306)
if [ -n "$DB_HOST" ]; then
  echo "[entrypoint] Aguardando banco em $DB_HOST:$DB_PORT..."
  : ${DB_PORT:=3306}
  if command -v nc >/dev/null 2>&1; then
    ATTEMPTS=0
    until nc -z "$DB_HOST" "$DB_PORT" 2>/dev/null; do
      ATTEMPTS=$((ATTEMPTS+1))
      if [ $ATTEMPTS -gt 60 ]; then
        echo "[entrypoint] Timeout aguardando banco (nc)" >&2
        break
      fi
      sleep 2
    done
  fi
  # Se nc não existir ou não conectou, tenta fallback Python
  python - <<PY || { echo "[entrypoint] Falha ao conectar no banco" >&2; exit 1; }
import os, socket, time, sys
h=os.environ.get('DB_HOST','db'); p=int(os.environ.get('DB_PORT','3306'))
for i in range(120):
    try:
        with socket.create_connection((h,p),2):
            print('[entrypoint] Banco acessível')
            break
    except OSError:
        time.sleep(1)
else:
    print('[entrypoint] Timeout aguardando banco (fallback python)', file=sys.stderr)
    sys.exit(1)
PY
fi

echo "[entrypoint] Aplicando migrações..."
python manage.py migrate --noinput

if [ "${COLLECT_STATIC:-1}" = "1" ]; then
  # Garante diretórios e permissões (se root)
  if [ "$(id -u)" = "0" ]; then
    mkdir -p staticfiles media || true
    chown -R appuser:appuser staticfiles media || true
  fi
  echo "[entrypoint] Coletando arquivos estáticos..."
  python manage.py collectstatic --noinput || echo "[entrypoint] collectstatic falhou (ignorado)"
  echo "[entrypoint] Sincronizando assets Vite (static/ -> staticfiles/)" 
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude '.*' static/ staticfiles/ 2>/dev/null || true
  else
    cp -a static/* staticfiles/ 2>/dev/null || true
  fi
  # Verificação simples
  ls -1 staticfiles/react/assets 2>/dev/null | head -n 5 || echo "[entrypoint] Aviso: assets Vite não encontrados em staticfiles/react/assets"

  # Guard extra: se o volume estático (montado) estiver praticamente vazio, repopula.
  STATIC_GUARD_MIN=${STATIC_GUARD_MIN:-10}
  COUNT_ITEMS=$(find staticfiles -mindepth 1 -maxdepth 2 -type f 2>/dev/null | wc -l | tr -d ' ')
  if [ "${COUNT_ITEMS:-0}" -lt "$STATIC_GUARD_MIN" ]; then
    echo "[entrypoint] Guard: staticfiles parece vazio ($COUNT_ITEMS < $STATIC_GUARD_MIN). Reforçando cópia de static/."
    if command -v rsync >/dev/null 2>&1; then
      rsync -a static/ staticfiles/ 2>/dev/null || true
    else
      cp -a static/* staticfiles/ 2>/dev/null || true
    fi
    COUNT_ITEMS=$(find staticfiles -mindepth 1 -maxdepth 2 -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "[entrypoint] Guard: itens após repopular = $COUNT_ITEMS"
    [ "$COUNT_ITEMS" -lt "$STATIC_GUARD_MIN" ] && echo "[entrypoint] Guard: ainda parece vazio; verifique permissões ou volume" || true
  fi
  # Marca de que rodamos processo de preparação
  touch staticfiles/.static_ready 2>/dev/null || true
fi

echo "[entrypoint] Rodando checagem Django..."
python manage.py check --deploy || echo "[entrypoint] Aviso: check --deploy retornou warnings"

echo "[entrypoint] Iniciando Gunicorn..."
if [ "$(id -u)" = "0" ]; then
  # Droppa privilégios para appuser
  exec su -s /bin/sh appuser -c "gunicorn samu_q.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout ${GUNICORN_TIMEOUT:-60} --access-logfile - --error-logfile -"
else
  exec gunicorn samu_q.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" --timeout "${GUNICORN_TIMEOUT:-60}" --access-logfile - --error-logfile -
fi
