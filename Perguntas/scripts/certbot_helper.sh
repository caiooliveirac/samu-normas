#!/usr/bin/env bash
set -euo pipefail

# Helper para emissão e renovação de certificados Let's Encrypt usando o serviço certbot do docker-compose.
# Pré-requisitos:
#  - DNS do domínio apontando para o servidor (A/AAAA) antes da emissão
#  - Porta 80 acessível externamente (para validação HTTP-01) na primeira emissão
#  - Após sucesso, atualizar nginx/default.conf substituindo SEU_DOMINIO e reiniciar nginx
#  - Em produção trocar mapeamento 8443:443 por 443:443
#
# Modos:
#  ./scripts/certbot_helper.sh issue exemplo.com contato@exemplo.com
#  ./scripts/certbot_helper.sh issue-prod exemplo.com contato@exemplo.com   # Sem --staging
#  ./scripts/certbot_helper.sh renew
#  ./scripts/certbot_helper.sh test-renew
#
# NOTA: Para múltiplos domínios adicionar -d adicional (ex: -d www.exemplo.com)

compose_file="docker-compose.prod.yml"
service="certbot"

log() { echo "[certbot-helper] $*"; }

require_args() {
  if [ "$#" -lt 2 ]; then
    echo "Uso: $0 issue <DOMINIO> <EMAIL>" >&2
    exit 1
  fi
}

case "${1:-}" in
  issue)
    shift
    require_args "$@"
    domain="$1"; email="$2";
    log "Emitindo certificado STAGING para $domain"
    docker compose -f "$compose_file" run --rm "$service" \
      certonly --standalone \
      -d "$domain" \
      --email "$email" --agree-tos --no-eff-email --staging
    ;;
  issue-prod)
    shift
    require_args "$@"
    domain="$1"; email="$2";
    log "Emitindo certificado PRODUCAO para $domain"
    docker compose -f "$compose_file" run --rm "$service" \
      certonly --standalone \
      -d "$domain" \
      --email "$email" --agree-tos --no-eff-email
    ;;
  renew)
    log "Renovando certificados (produção)"
    docker compose -f "$compose_file" run --rm "$service" renew --quiet
    ;;
  test-renew)
    log "Testando processo de renovação (dry-run)"
    docker compose -f "$compose_file" run --rm "$service" renew --dry-run
    ;;
  *)
    cat <<EOF
Uso:
  $0 issue <DOMINIO> <EMAIL>       # Emissão inicial (staging)
  $0 issue-prod <DOMINIO> <EMAIL>   # Emissão inicial (produção)
  $0 renew                          # Renovação (crontab mensal)
  $0 test-renew                     # Testar renovação sem efetivar
EOF
    exit 1
    ;;
 esac

log "Concluído"
