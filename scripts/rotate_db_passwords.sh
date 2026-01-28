#!/usr/bin/env bash
set -euo pipefail

# Este script gera novas senhas para o usuário de aplicação e root do MariaDB
# e aplica no banco em execução via docker-compose.prod.yml.
# Requisitos: variáveis de ambiente DB_USER, DB_HOST (ou defaults) e acesso ao container db.
# Uso:
#   ./scripts/rotate_db_passwords.sh [--print-only]
#   (opcional) export COMPOSE_FILE=docker-compose.prod.yml
#
# Ele NÃO edita automaticamente seus arquivos .env; imprime as novas senhas para você atualizar manualmente.

COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.prod.yml}
APP_USER=${DB_USER:-samu_q}
DB_HOST=${DB_HOST:-db}

print_only=false
if [[ "${1:-}" == "--print-only" ]]; then
  print_only=true
fi

rand() {
  # Gera token seguro URL-safe
  python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
}

NEW_APP_PASS="db-$(rand)"
NEW_ROOT_PASS="root-$(rand)"

if $print_only; then
  echo "(PRINT ONLY) DB_PASSWORD=${NEW_APP_PASS}"
  echo "(PRINT ONLY) DB_ROOT_PASSWORD=${NEW_ROOT_PASS}"
  exit 0
fi

echo "== Gerando e aplicando novas senhas =="
echo "Usuário aplicação: $APP_USER"

# 1. Aplica nova senha root primeiro (usa senha root atual via variável DB_ROOT_PASSWORD)
if [[ -z "${DB_ROOT_PASSWORD:-}" ]]; then
  echo "ERRO: export DB_ROOT_PASSWORD com a senha root atual antes de rodar." >&2
  exit 1
fi

# Executa ALTER USER dentro do container db
set -x
docker compose -f "$COMPOSE_FILE" exec -T db mariadb -uroot -p"$DB_ROOT_PASSWORD" -e \
  "ALTER USER 'root'@'%' IDENTIFIED BY '${NEW_ROOT_PASS}'; FLUSH PRIVILEGES;"

docker compose -f "$COMPOSE_FILE" exec -T db mariadb -uroot -p"${NEW_ROOT_PASS}" -e \
  "ALTER USER '${APP_USER}'@'%' IDENTIFIED BY '${NEW_APP_PASS}'; FLUSH PRIVILEGES;"
set +x

echo
echo "== Novas credenciais =="
echo "DB_PASSWORD=${NEW_APP_PASS}"
echo "DB_ROOT_PASSWORD=${NEW_ROOT_PASS}"
echo
cat <<'EOF'
Atualize agora:
  - .env e/ou .env.prod (DB_PASSWORD / DB_ROOT_PASSWORD)
  - Reinicie o serviço web: docker compose -f docker-compose.prod.yml up -d --no-deps --build web
  - Se for rotacionar também a SECRET_KEY, substitua e reinicie (sessões serão invalidadas).

Guarde as senhas em um cofre seguro e NÃO as versione.
EOF
