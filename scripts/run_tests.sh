#!/usr/bin/env bash
set -euo pipefail

# Uso:
#   DB_ENGINE=sqlite ./scripts/run_tests.sh            # usa venv .venv (cria se não existir)
# Variáveis:
#   DB_ENGINE=sqlite|mysql (default sqlite para testes rápidos)
#   NO_RUFF=1  (pula lint)

PROJECT_ROOT="$(cd "$(dirname "$0")"/.. && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f requirements-dev.txt ]]; then
  echo "[ERRO] requirements-dev.txt não encontrado em $(pwd)" >&2
  exit 1
fi

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[ERRO] Python não encontrado (procurei por '$PYTHON_BIN')." >&2
  exit 1
fi

if [[ ! -d "$VENV_DIR" ]]; then
  echo "==> Criando virtualenv em $VENV_DIR" >&2
  if ! "$PYTHON_BIN" -m venv "$VENV_DIR" 2>/dev/null; then
    echo "[AVISO] Módulo venv indisponível. Usando fallback user site-packages (.pip-local)." >&2
    export PIP_TARGET=".pip-local"
    mkdir -p "$PIP_TARGET"
    export PYTHONPATH="$PIP_TARGET:$PYTHONPATH"
    USE_FALLBACK=1
  fi
fi

if [[ -z "${USE_FALLBACK:-}" && -d "$VENV_DIR" && -f "$VENV_DIR/bin/activate" ]]; then
  # Só ativa se o script existir de fato
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
else
  # criar função pip wrapper usando python base
  pip() { "$PYTHON_BIN" -m pip "$@"; }
fi

# Garantir pip funcional
if ! "$PYTHON_BIN" -m pip --version >/dev/null 2>&1; then
  echo "==> Instalando pip (fallback)" >&2
  curl -sS https://bootstrap.pypa.io/get-pip.py | "$PYTHON_BIN" -
fi

echo "==> Atualizando pip (silencioso)" >&2
"$PYTHON_BIN" -m pip install -q --upgrade pip

echo "==> Instalando dependências de desenvolvimento" >&2
if [[ -n "${USE_FALLBACK:-}" && "${DB_ENGINE:-sqlite}" == "sqlite" ]]; then
  echo "[INFO] Fallback + SQLite: instalando sem mysqlclient para evitar build nativo." >&2
  TMP_REQ=.tmp-reqs.txt
  : > "$TMP_REQ"
  # requirements.txt sem mysqlclient
  while IFS= read -r line; do
    [[ "$line" =~ ^mysqlclient ]] && continue
    echo "$line" >> "$TMP_REQ"
  done < requirements.txt
  # requirements-dev.txt sem linha -r
  while IFS= read -r line; do
    [[ "$line" =~ ^-r ]] && continue
    echo "$line" >> "$TMP_REQ"
  done < requirements-dev.txt
  "$PYTHON_BIN" -m pip install --break-system-packages --no-warn-script-location --upgrade -q -r "$TMP_REQ"
else
  "$PYTHON_BIN" -m pip install --break-system-packages -q -r requirements-dev.txt
fi

export DB_ENGINE=${DB_ENGINE:-sqlite}

if [[ -z "${NO_RUFF:-}" ]]; then
  echo "==> Lint (ruff)" >&2
  ruff check . || { echo "Falha no lint" >&2; exit 1; }
fi

echo "==> Pytest (DB_ENGINE=$DB_ENGINE)" >&2
pytest --cov=questions --cov=faq --cov-report=term-missing -q

echo "==> Sucesso" >&2
