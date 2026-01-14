#!/usr/bin/env bash
set -euo pipefail

# Deploy simplificado.
# Uso:
#   APP_IMAGE=ghcr.io/OWNER/REPO/samu-normas:<tag> ./scripts/deploy.sh
# Ou para build local (sem APP_IMAGE definido):
#   ./scripts/deploy.sh --build-local
# Flags:
#   --build-local      Faz build local da imagem web
#   --force-recreate   Força recriação dos serviços web/nginx
#   --no-migrate       Pula migrações (normalmente entrypoint já faz migrate)
#   --pull-only        Apenas faz pull da imagem (não sobe stack)
#   --health-url URL   URL para healthcheck final (default http://localhost/nginx-health)

COMPOSE_FILE="docker-compose.prod.yml"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

BUILD_LOCAL=false
FORCE_RECREATE=false
NO_MIGRATE=false
PULL_ONLY=false
HEALTH_URL="http://localhost/nginx-health"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --build-local) BUILD_LOCAL=true; shift ;;
    --force-recreate) FORCE_RECREATE=true; shift ;;
    --no-migrate) NO_MIGRATE=true; shift ;;
    --pull-only) PULL_ONLY=true; shift ;;
    --health-url) HEALTH_URL="$2"; shift 2 ;;
    *) echo "[deploy] Flag desconhecida: $1"; exit 1 ;;
  esac
done

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "[deploy] Arquivo $COMPOSE_FILE não encontrado (execute dentro de Perguntas)" >&2
  exit 1
fi

if [[ -n "${APP_IMAGE:-}" ]]; then
  echo "[deploy] Usando imagem externa: $APP_IMAGE"
  if ! $BUILD_LOCAL; then
    echo "[deploy] Fazendo pull da imagem..."
    docker compose -f "$COMPOSE_FILE" pull web || true
  fi
else
  echo "[deploy] APP_IMAGE não definido. Modo build local."
  BUILD_LOCAL=true
fi

if $PULL_ONLY; then
  echo "[deploy] Pull realizado. Encerrando (--pull-only)."
  exit 0
fi

if $BUILD_LOCAL; then
  echo "[deploy] Build local da imagem web..."
  # Metadados de build para auditoria e para o endpoint /__version__.
  # Só é usado no build local; em pull-based a imagem já deve ter isso embutido pelo CI.
  export BUILD_SHA
  BUILD_SHA="$(git rev-parse --short=12 HEAD 2>/dev/null || echo dev-local)"
  export BUILD_DATE
  BUILD_DATE="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
  export APP_VERSION
  APP_VERSION="$(git describe --tags --always --dirty 2>/dev/null || echo dev)"
  echo "[deploy] Build metadata: BUILD_SHA=$BUILD_SHA APP_VERSION=$APP_VERSION BUILD_DATE=$BUILD_DATE"
  docker compose -f "$COMPOSE_FILE" build web
fi

UP_FLAGS=(-d)
$FORCE_RECREATE && UP_FLAGS+=(--force-recreate)

echo "[deploy] Subindo stack (serviços principais)..."
docker compose -f "$COMPOSE_FILE" up "${UP_FLAGS[@]}" db web nginx

echo "[deploy] Aguardando web saudável..."
ATTEMPTS=0
until curl -sf "$HEALTH_URL" >/dev/null 2>&1; do
  ATTEMPTS=$((ATTEMPTS+1))
  if (( ATTEMPTS > 60 )); then
    echo "[deploy] Timeout aguardando health URL: $HEALTH_URL" >&2
    docker compose -f "$COMPOSE_FILE" logs --tail=100 web || true
    exit 1
  fi
  sleep 2
  [[ $((ATTEMPTS%10)) -eq 0 ]] && echo "[deploy] ainda aguardando (${ATTEMPTS})..."
done

echo "[deploy] Health OK: $HEALTH_URL"

if ! $NO_MIGRATE; then
  echo "[deploy] (Opcional) Migrações já executadas no entrypoint; para forçar manual:"
  echo "          docker compose -f $COMPOSE_FILE exec web python manage.py migrate"
fi

echo "[deploy] Finalizado com sucesso."
