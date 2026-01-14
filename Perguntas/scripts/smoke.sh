#!/usr/bin/env bash
set -euo pipefail

# Smoke test para stack Django + Nginx + MariaDB + React.
# Requisitos:
# - Docker e docker compose disponíveis.
# - Executado a partir do diretório raiz (onde está docker-compose.prod.yml) ou ajuste COMPOSE_FILE.
# - Usa APP_IMAGE se exportado (para validar imagem pull-based), senão segue compose atual.
# - NÃO roda migrations destrutivas; apenas verifica idempotência e health.
# - Cria/usa um usuário 'smoketest' para checar persistência de DB.

usage() {
  cat <<EOF
Uso: ALLOW_SMOKE=1 ./scripts/smoke.sh [--compose-file <arquivo>] [--host http://localhost]
Variáveis:
  ALLOW_SMOKE=1        Confirma que entende que este script fará restart do serviço web.
Opções:
  --compose-file <arq>  (default: Perguntas/docker-compose.prod.yml)
  --host <url_base>     (default: http://localhost)
  --skip-restart        Não reinicia o container web (apenas validações leves)
  --no-color            Desabilita cores
EOF
}

if [[ "${ALLOW_SMOKE:-}" != 1 ]]; then
  echo "[ERRO] Defina ALLOW_SMOKE=1 para executar (proteção)." >&2
  exit 2
fi

COMPOSE_FILE="Perguntas/docker-compose.prod.yml"
COMPOSE_FILES=""
BASE_HOST="http://localhost"
RESTART=1
COLOR=1

while [[ $# -gt 0 ]]; do
  case "$1" in
  --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
    --host) BASE_HOST="$2"; shift 2 ;;
    --skip-restart) RESTART=0; shift ;;
    --no-color) COLOR=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Opção desconhecida: $1"; usage; exit 1 ;;
  esac
done

# Cores
if [[ $COLOR -eq 1 ]]; then
  B='\033[1;34m'; G='\033[1;32m'; Y='\033[1;33m'; R='\033[1;31m'; Z='\033[0m'
else
  B=''; G=''; Y=''; R=''; Z=''
fi

log() { echo -e "${B}[*]${Z} $*"; }
ok() { echo -e "${G}[OK]${Z} $*"; }
warn() { echo -e "${Y}[WARN]${Z} $*"; }
fail() { echo -e "${R}[FAIL]${Z} $*"; exit 1; }

compose() {
  if [[ -n "$COMPOSE_FILES" ]]; then
    # Monta array de argumentos -f para cada arquivo
    local args=()
    IFS=',' read -r -a files <<< "$COMPOSE_FILES"
    for f in "${files[@]}"; do
      args+=( -f "$f" )
    done
    docker compose "${args[@]}" "$@"
  else
    docker compose -f "$COMPOSE_FILE" "$@"
  fi
}

if [[ -n "$COMPOSE_FILES" ]]; then
  log "Arquivos compose: $COMPOSE_FILES"
else
  log "Arquivo compose: $COMPOSE_FILE"
fi
log "Host base: $BASE_HOST"

log "1. Verificando serviços em execução"
compose ps >/dev/null || fail "docker compose ps falhou"

log "2. Health Nginx"
curl -sf "$BASE_HOST/nginx-health" >/dev/null && ok "nginx-health 200" || fail "nginx-health falhou"

log "3. Health Django"
curl -sf "$BASE_HOST/healthz" >/dev/null && ok "healthz 200" || fail "healthz falhou"

log "4. Verificando asset React principal"
ASSET=$(compose exec -T web /bin/sh -c "ls static/react/assets/main-*.js 2>/dev/null | head -n1" || true)
if [[ -z "$ASSET" ]]; then
  fail "Asset main-*.js não encontrado em static/react/assets"
fi
curl -sf "$BASE_HOST/static/react/assets/$(basename "$ASSET")" >/dev/null && ok "Asset $(basename "$ASSET") servido" || fail "Falha ao acessar asset"

log "5. Migrações idempotentes (plan)"
compose exec -T web python manage.py migrate --plan | grep -q "No planned migration" && ok "Nenhuma migration pendente" || warn "Há migrations planejadas (verifique)"

log "6. Usuário smoketest (persistência)"
CREATE_OUTPUT=$(compose exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model; U=get_user_model(); import sys; obj,created=U.objects.get_or_create(username='smoketest'); print('created' if created else 'exists')")
if [[ "$CREATE_OUTPUT" == "created" ]]; then
  ok "Usuário smoketest criado"
else
  ok "Usuário smoketest já existia"
fi

if [[ $RESTART -eq 1 ]]; then
  log "7. Restart apenas do web"
  compose restart web || fail "Restart web falhou"
  # Espera progressiva pelo Gunicorn subir
  ATTEMPTS=0; MAX_ATTEMPTS=12; SLEEP=2
  until curl -sf "$BASE_HOST/healthz" >/dev/null; do
    ATTEMPTS=$((ATTEMPTS+1))
    if [[ $ATTEMPTS -ge $MAX_ATTEMPTS ]]; then
      fail "healthz falhou pós-restart (timeout ~$((ATTEMPTS*SLEEP))s)"
    fi
    sleep $SLEEP
  done
  ok "healthz pós-restart (em ${ATTEMPTS} tentativas)"
  if compose exec -T web python manage.py shell -c "from django.contrib.auth import get_user_model as gum; U=gum(); import sys; sys.exit(0 if U.objects.filter(username='smoketest').exists() else 1)"; then
    ok "Usuário smoketest persiste após restart"
  else
    fail "Usuário smoketest sumiu após restart"
  fi
else
  warn "Pulado restart (flag --skip-restart)"
fi

log "8. Resumo"
cat <<RES
Health Nginx: OK
Health Django: OK
Asset React: OK ($ASSET)
User smoketest: OK (persistente)
Restart web: $( [[ $RESTART -eq 1 ]] && echo OK || echo SKIPPED )
RES

ok "Smoke test concluído"
