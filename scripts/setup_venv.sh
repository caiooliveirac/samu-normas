#!/usr/bin/env bash
set -euo pipefail

# Cria ambiente virtual Python com pip disponível mesmo em sistemas mínimos sem python3-venv instalado globalmente.
# Estratégia:
# 1. Detectar python3 disponível.
# 2. Tentar criar venv normal. Se falhar por ensurepip ausente, baixar get-pip.py e bootstrap dentro de diretório isolado.
# 3. Instalar requirements básicos.
# Uso:
#   ./scripts/setup_venv.sh            # cria .venv e instala requirements.txt
#   ./scripts/setup_venv.sh dev        # também instala requirements-dev.txt
#   source .venv/bin/activate
#
# Não requer sudo.

MODE=${1:-base}
PYTHON_BIN=${PYTHON_BIN:-python3}
VENV_DIR=.venv

log() { echo -e "\033[1;34m[setup_venv]\033[0m $*"; }
warn() { echo -e "\033[1;33m[warn]\033[0m $*"; }
fail() { echo -e "\033[1;31m[fail]\033[0m $*"; exit 1; }

command -v "$PYTHON_BIN" >/dev/null || fail "Python não encontrado (variável PYTHON_BIN)."

if [[ -d "$VENV_DIR" ]]; then
  log "Ambiente virtual já existe: $VENV_DIR (remova se quiser recriar)"
  exit 0
fi

log "Tentando criar venv padrão..."
if "$PYTHON_BIN" -m venv "$VENV_DIR" 2>/tmp/venv_err.log; then
  log "Venv criada com sucesso."
else
  warn "Falhou criar venv convencional. Tentando fallback manual."
  mkdir -p "$VENV_DIR"
  # Cria estrutura mínima
  "$PYTHON_BIN" -c "import sys,venv,os; builder=venv.EnvBuilder(with_pip=False); builder.create('.venv')" || fail "Falha na criação manual do esqueleto venv"
  log "Baixando get-pip.py"
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py || fail "Download get-pip.py falhou"
  "$PYTHON_BIN" /tmp/get-pip.py --prefix "$PWD/$VENV_DIR" || "$PYTHON_BIN" /tmp/get-pip.py --user || fail "Bootstrap pip falhou"
fi

# Ativa
if [[ -f "$VENV_DIR/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
else
  fail "Arquivo activate não encontrado em $VENV_DIR/bin/activate"
fi

# Verifica pip
if ! command -v pip >/dev/null; then
  fail "pip não disponível mesmo após bootstrap"
fi

log "pip versão: $(pip --version)"

log "Instalando requirements.txt (produção/base)"
pip install -q -r Perguntas/requirements.txt

if [[ "$MODE" == "dev" ]]; then
  if [[ -f Perguntas/requirements-dev.txt ]]; then
    log "Instalando requirements-dev.txt"
    pip install -q -r Perguntas/requirements-dev.txt
  else
    warn "requirements-dev.txt não encontrado"
  fi
fi

log "Ambiente pronto. Ative com: source $VENV_DIR/bin/activate"
