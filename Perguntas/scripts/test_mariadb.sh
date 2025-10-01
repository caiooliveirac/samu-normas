#!/usr/bin/env bash
set -euo pipefail
# Executa testes Django usando MariaDB real do docker-compose.
# Usa DB_TEST_NAME se definido (senão <DB_NAME>_test).
# Torna-se não interativo: sempre recria o banco de teste quando ALWAYS_DROP_TEST_DB=1 (default 1).
# Variáveis de ambiente suportadas:
#   DB_NAME, DB_TEST_NAME, DB_ROOT_PASSWORD, DB_USER
#   REBUILD_WEB=1 para forçar rebuild da imagem web
#   ALWAYS_DROP_TEST_DB=1 força dropar DB de teste antes de criar (padrão 1)
#   KEEP_DB=1 ignora drop mesmo se ALWAYS_DROP_TEST_DB=1
# Pré-requisitos: docker-compose.prod.yml, serviços db e web.

COMPOSE_FILE=${COMPOSE_FILE:-docker-compose.prod.yml}
DB_NAME=${DB_NAME:-samu_q}
DB_TEST_NAME=${DB_TEST_NAME:-${DB_NAME}_test}
DB_ROOT_PASSWORD=${DB_ROOT_PASSWORD:-}
REBUILD_WEB=${REBUILD_WEB:-0}
ALWAYS_DROP_TEST_DB=${ALWAYS_DROP_TEST_DB:-1}

if [[ -z "$DB_ROOT_PASSWORD" ]]; then
  echo "[ERRO] Exporte DB_ROOT_PASSWORD para criar/verificar banco de teste" >&2
  exit 2
fi

if [[ "$REBUILD_WEB" == "1" ]]; then
  echo "[INFO] Rebuild da imagem web solicitado (REBUILD_WEB=1)"
  docker compose -f "$COMPOSE_FILE" build web
fi

echo "[INFO] Subindo serviços necessários (db, web)"
docker compose -f "$COMPOSE_FILE" up -d db web

echo "[INFO] Aguardando banco ficar saudável..."
for i in {1..30}; do
  if docker compose -f "$COMPOSE_FILE" exec -T db mariadb -uroot -p"$DB_ROOT_PASSWORD" -e 'SELECT 1' >/dev/null 2>&1; then
    break
  fi
  sleep 2
  if [[ $i -eq 30 ]]; then
    echo "[ERRO] Banco não ficou pronto" >&2; exit 3
  fi
done

if [[ "$ALWAYS_DROP_TEST_DB" == "1" && "${KEEP_DB:-0}" != "1" ]]; then
  echo "[INFO] Dropando database de teste (se existir): $DB_TEST_NAME"
  docker compose -f "$COMPOSE_FILE" exec -T db mariadb -uroot -p"$DB_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS \`$DB_TEST_NAME\`;"
fi

echo "[INFO] (Re)criando database de teste: $DB_TEST_NAME"
docker compose -f "$COMPOSE_FILE" exec -T db mariadb -uroot -p"$DB_ROOT_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS \`$DB_TEST_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON \`$DB_TEST_NAME\`.* TO '${DB_USER:-samu_q}'@'%'; FLUSH PRIVILEGES;"

echo "[INFO] Executando testes (MySQL/MariaDB) -- noinput"
docker compose -f "$COMPOSE_FILE" exec -e DB_ENGINE=mysql -e DB_TEST_NAME="$DB_TEST_NAME" web python manage.py test --noinput "$@"
