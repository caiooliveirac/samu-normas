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

# ── Auto-seed: se a tabela de regras existir mas estiver vazia, popula a partir do fixture ──
# Isso resolve o problema recorrente de dados não carregarem após deploy/recreate de volumes.
# Para forçar re-seed manual: FORCE_SEED=1  ou  python manage.py seed_rules --fresh
SEED_FIXTURE="${SEED_FIXTURE:-rules_seed.json}"
FORCE_SEED="${FORCE_SEED:-0}"

RULE_COUNT=$(python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE','samu_q.settings')
django.setup()
try:
    from questions.models import Rule
    print(Rule.objects.count())
except Exception:
    print('0')
" 2>/dev/null || echo "0")

if [ "$FORCE_SEED" = "1" ] || [ "$RULE_COUNT" = "0" ]; then
  if [ -f "$SEED_FIXTURE" ]; then
    echo "[entrypoint] Tabela de regras vazia (count=$RULE_COUNT) ou FORCE_SEED=1. Executando seed_rules..."
    python manage.py seed_rules --fixture "$SEED_FIXTURE" --fresh || echo "[entrypoint] AVISO: seed_rules falhou"
  else
    echo "[entrypoint] AVISO: Tabela de regras vazia mas fixture '$SEED_FIXTURE' não encontrada. Dados NÃO carregados."
  fi
else
  echo "[entrypoint] Regras já populadas ($RULE_COUNT registros). Pulando seed."
fi

if [ "${COLLECT_STATIC:-1}" = "1" ]; then
  # Garante diretórios e permissões (se root)
  if [ "$(id -u)" = "0" ]; then
    mkdir -p staticfiles media || true
    chown -R appuser:appuser staticfiles media || true
  fi
  # Em produção, o volume staticfiles deve ser a fonte de verdade. Se já estiver pronto,
  # evitamos sobrescrever com assets empacotados antigos em reinícios/recreates.
  FORCE_COLLECT_STATIC=${FORCE_COLLECT_STATIC:-0}
  STATIC_GUARD_MIN=${STATIC_GUARD_MIN:-10}
  COUNT_ITEMS=$(find staticfiles -mindepth 1 -maxdepth 2 -type f 2>/dev/null | wc -l | tr -d ' ')
  if [ "$FORCE_COLLECT_STATIC" != "1" ] && [ -f staticfiles/.static_ready ] && [ "${COUNT_ITEMS:-0}" -ge "$STATIC_GUARD_MIN" ]; then
    echo "[entrypoint] Static já preparado (staticfiles/.static_ready + $COUNT_ITEMS itens). Pulando collectstatic/rsync."
  else
    echo "[entrypoint] Coletando arquivos estáticos..."
    python manage.py collectstatic --noinput || echo "[entrypoint] collectstatic falhou (ignorado)"
    echo "[entrypoint] Sincronizando static/ -> staticfiles/ (exceto react/)" 
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --exclude 'react/' --exclude 'react/**' --exclude '.*' static/ staticfiles/ 2>/dev/null || true
    else
      # Fallback sem rsync (não copia react/ para evitar sobrescrever volume dedicado)
      for p in static/*; do
        [ "$(basename "$p")" = "react" ] && continue
        cp -a "$p" staticfiles/ 2>/dev/null || true
      done
    fi
  fi
  # Verificação simples (manifest + assets)
  if [ -f static/react/.vite/manifest.json ]; then
    echo "[entrypoint] Manifest Vite OK: static/react/.vite/manifest.json"
  else
    echo "[entrypoint] Aviso: manifest Vite não encontrado em static/react/.vite/manifest.json"
  fi
  ls -1 static/react/assets 2>/dev/null | head -n 5 || true

  # Guard extra: se o volume estático (montado) estiver praticamente vazio, repopula.
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
