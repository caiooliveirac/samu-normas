#!/usr/bin/env bash
set -euo pipefail

# Executa testes em container Python isolado (sem tocar host).
# Uso: ./scripts/test_in_container.sh
# Variáveis opcionais:
#   PY_IMAGE=python:3.12-slim
#   DB_ENGINE=sqlite (recomendado para velocidade)
#   NO_RUFF=1  (pula lint)
#   CACHE_DIR=.cache/pip  (persistir cache pip via volume opcional)

PY_IMAGE=${PY_IMAGE:-python:3.12-slim}
DB_ENGINE=${DB_ENGINE:-sqlite}
PROJECT_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"

# Se quiser cache pip local: criar diretório e montar (-v "$CACHE_DIR":/root/.cache/pip)
CACHE_ARG=""
if [[ -n "${CACHE_DIR:-}" ]]; then
  mkdir -p "$CACHE_DIR"
  CACHE_ARG="-v $(realpath "$CACHE_DIR"):/root/.cache/pip"
fi

# Flags extras para pular ruff
EXTRA_ENV=""
if [[ -n "${NO_RUFF:-}" ]]; then
  EXTRA_ENV="-e NO_RUFF=1"
fi

# Rodamos no subdiretório Perguntas (código Django)
CMD='set -euo pipefail; \n \
  cd /workspace/Perguntas; \n \
  bash scripts/run_tests.sh'

echo "==> Pull/usar imagem $PY_IMAGE" >&2

docker run --rm \
  -e DB_ENGINE="$DB_ENGINE" \
  $EXTRA_ENV \
  -v "$PROJECT_ROOT":/workspace \
  $CACHE_ARG \
  -w /workspace/Perguntas \
  "$PY_IMAGE" bash -c "${CMD}" 

echo "==> Testes em container concluídos" >&2
