#!/usr/bin/env bash
set -euo pipefail
# Script de deploy pull-based para EC2.
# Requisitos:
#  - docker + docker compose plugin instalados
#  - login no GHCR realizado (docker login ghcr.io) ou usar token via stdin
#  - arquivo .env.prod presente (ou variáveis exportadas)
# Uso:
#   APP_TAG=sha_ou_branch ./scripts/deploy_pull.sh
# Variáveis:
#   APP_TAG (obrigatório) - tag da imagem (ex: latest, master, <sha>, v1.0.0)
#   REGISTRY_IMAGE (default: ghcr.io/caiooliveirac/samu-normas)
#   COMPOSE_FILE (default: docker-compose.prod.yml)
#   DRY_RUN=1 apenas imprime o que faria
#   NO_PULL=1 não executa docker pull (usa cache local)
#   NO_MIGRATE=1 pula migrations
#   NO_COLLECTSTATIC=1 pula collectstatic
#   FORCE_RECREATE=1 força recreate dos serviços (docker compose up -d --force-recreate)

REGISTRY_IMAGE=${REGISTRY_IMAGE:-ghcr.io/caiooliveirac/samu-normas}
COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.prod.yml}
APP_TAG=${APP_TAG:-}

if [[ -z "$APP_TAG" ]]; then
  echo "[ERRO] Defina APP_TAG (ex: APP_TAG=master $0)" >&2
  exit 2
fi

APP_IMAGE="$REGISTRY_IMAGE:$APP_TAG"
export APP_IMAGE

echo "[INFO] Deploy pull-based" 
echo "[INFO] Usando imagem: $APP_IMAGE"

if [[ "${DRY_RUN:-0}" == "1" ]]; then
  echo "[DRY] Encerrando por DRY_RUN=1"; exit 0
fi

if [[ "${NO_PULL:-0}" != "1" ]]; then
  echo "[INFO] Pull da imagem"
  docker pull "$APP_IMAGE"
else
  echo "[INFO] NO_PULL=1 — pulando docker pull"
fi

# Sobe/atualiza containers
UP_FLAGS=( -d )
if [[ "${FORCE_RECREATE:-0}" == "1" ]]; then
  UP_FLAGS+=( --force-recreate )
fi

echo "[INFO] Subindo serviços (docker compose -f $COMPOSE_FILE up ${UP_FLAGS[*]})"
docker compose -f "$COMPOSE_FILE" up "${UP_FLAGS[@]}"

# Rodar migrations e collectstatic dentro do container web
WEB_SERVICE=${WEB_SERVICE:-web}

if [[ "${NO_MIGRATE:-0}" != "1" ]]; then
  echo "[INFO] Aplicando migrations"
  docker compose -f "$COMPOSE_FILE" exec "$WEB_SERVICE" python manage.py migrate --noinput
else
  echo "[INFO] NO_MIGRATE=1 — pulando migrations"
fi

# Auto-seed: se a tabela de regras estiver vazia, executa seed_rules automaticamente.
# Isso garante que dados apareçam no frontend após deploy limpo ou recreate de volumes.
if [[ "${NO_SEED:-0}" != "1" ]]; then
  RULE_COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T "$WEB_SERVICE" python -c "
import django,os;os.environ.setdefault('DJANGO_SETTINGS_MODULE','samu_q.settings');django.setup()
from questions.models import Rule;print(Rule.objects.count())
" 2>/dev/null || echo "0")
  if [[ "$RULE_COUNT" == "0" ]]; then
    echo "[INFO] Tabela de regras vazia. Executando seed_rules..."
    docker compose -f "$COMPOSE_FILE" exec "$WEB_SERVICE" python manage.py seed_rules --fresh || echo "[WARN] seed_rules falhou"
  else
    echo "[INFO] Regras já populadas ($RULE_COUNT registros). Pulando seed."
  fi
else
  echo "[INFO] NO_SEED=1 — pulando seed"
fi

if [[ "${NO_COLLECTSTATIC:-0}" != "1" ]]; then
  echo "[INFO] Executando collectstatic"
  docker compose -f "$COMPOSE_FILE" exec "$WEB_SERVICE" python manage.py collectstatic --noinput
else
  echo "[INFO] NO_COLLECTSTATIC=1 — pulando collectstatic"
fi

echo "[INFO] Deploy finalizado com sucesso"
