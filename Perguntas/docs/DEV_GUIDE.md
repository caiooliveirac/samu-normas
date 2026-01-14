# Guia de Desenvolvimento e Operações

Este documento consolida o conhecimento necessário para voltar a trabalhar neste projeto sem depender do histórico da sessão anterior.

## 1. Visão Geral
- Backend: Django (projeto `samu_q`, apps principais: `questions`, `faq`).
- Frontend: React + Vite (`frontend/`). Build gera assets em `static/react`.
- Banco Produção: MariaDB. Testes rápidos usam SQLite.
- Servidor: Gunicorn + Nginx (conf em `nginx/default.conf`).
- Containerização: Docker multi-stage (`Dockerfile.prod`).
- Registro de Imagens: GHCR (`ghcr.io/caiooliveirac/samu-normas`).
- Seed inicial de dados: comando `seed_rules` lendo `rules_seed.json`.
- Testes: pytest + pytest-django.

## 2. Estrutura Importante
```
Perguntas/
  manage.py
  samu_q/ (settings, urls, wsgi, asgi)
  questions/ (models, views, management commands)
  faq/
  frontend/ (src React)
  static/ (arquivos estáticos gerados)
  scripts/ (scripts utilitários)
  rules_seed.json
  rules_fixture.json (possível base de comparação)
  docker-compose.prod.yml
  docker-compose.dev.yml
  Dockerfile.prod
```

## 3. Ambiente de Desenvolvimento Local
Opção 1 — Docker Compose (recomendado):
```
cp .env.example .env  # se existir template
# Ajustar variáveis necessárias
docker compose -f docker-compose.dev.yml up --build
```

Opção 2 — Venv local:
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # se houver
python manage.py migrate
python manage.py runserver
```

## 4. Variáveis de Ambiente (principais)
- `DJANGO_SETTINGS_MODULE=samu_q.settings`
- `SECRET_KEY` (definir em produção)
- `DEBUG` (false em produção)
- `DATABASE_URL` OU variáveis separadas de MariaDB (host, user, password, db)
- `ALLOWED_HOSTS` (incluindo domínio e localhost)
- `CSRF_TRUSTED_ORIGINS` (com https://dominio)
- `APP_IMAGE` (usado em compose de produção para fixar versão)

## 5. Seed de Dados
Comando customizado: `python manage.py seed_rules`

Uso típico após migrações:
```
python manage.py migrate
python manage.py seed_rules --fresh
```

### Fluxo rápido (sem rebuild) para testar conteúdo
Quando você está só ajustando o conteúdo (Markdown/seed) e quer evitar esperar build de imagem, use o override [docker-compose.prod.override.dev-seed.yml](docker-compose.prod.override.dev-seed.yml) que faz bind-mount do `rules_seed.json` dentro do container `web`.

1) Suba o stack usando a imagem já existente (sem build):
```
docker compose -f docker-compose.prod.yml -f docker-compose.prod.override.dev-seed.yml up -d --no-build
```

2) Gere/atualize o seed no host (ex.: via Markdown) e aplique no banco:
```
python scripts/md_manual_to_rules_seed.py --md docs/manual_draft_from_seed_preview.md --out rules_seed.json
docker compose -f docker-compose.prod.yml -f docker-compose.prod.override.dev-seed.yml exec web python manage.py seed_rules --fresh --fixture rules_seed.json
```

Observação: como é bind-mount, qualquer alteração no `rules_seed.json` do host aparece imediatamente no container (em geral não precisa reiniciar).
Internamente:
- Lê `rules_seed.json`
- Converte FKs numéricas para `<campo>_id`
- Cria objetos em ordem para prevenir falhas
- Aplica M2M (ex: tags) após salvar

## 6. Testes
Scripts úteis em `scripts/`:
- `run_tests.sh`: tenta usar venv se existir, fallback direto.
- `test_in_container.sh`: roda testes em container python isolado.

Execução:
```
bash scripts/run_tests.sh
# ou
bash scripts/test_in_container.sh
```

Banco em testes: SQLite (rápido, não depende de MariaDB). Para testar MariaDB especificamente, ajustar settings ou variáveis.
Endpoint de versão disponível após build: `GET /__version__` retorna JSON:
```json
{
  "sha": "<commit>",
  "version": "<tag-ou-sha>",
  "build_date": "<ISO8601>"
}
```

## 7. Build de Imagem
Multi-stage: Node (frontend) -> Python build wheels -> Final runtime.

Build manual local:
```
export REPO=ghcr.io/caiooliveirac/samu-normas
export VERSION=v0.2.0
export SHA=$(git rev-parse --short=12 HEAD)
export DATE_TAG=$(date +%Y%m%d-%H%M%S)
export GHCR_TOKEN='SEU_TOKEN_COM_write:packages'
echo "$GHCR_TOKEN" | docker login ghcr.io -u caiooliveirac --password-stdin

docker buildx build \
  -f Dockerfile.prod \
  --platform linux/arm64 \
  -t $REPO:latest \
  -t $REPO:$VERSION \
  -t $REPO:$SHA \
  -t $REPO:$DATE_TAG \
  --push \
  .
```

Verificação:
```
docker pull $REPO:$VERSION
docker inspect $REPO:$VERSION --format '{{.Id}} {{.RepoDigests}}'
```

## 8. Versionamento e Tags
- Criar release: `git tag vX.Y.Z && git push origin vX.Y.Z`
- Tags de imagem: `vX.Y.Z`, `latest`, SHA curto, timestamp.
- Em produção usar sempre tag imutável (`vX.Y.Z` ou SHA).

## 9. Deploy Produção
Assumindo `docker-compose.prod.yml` e MariaDB externa/serviço:
```
export APP_IMAGE=ghcr.io/caiooliveirac/samu-normas:v0.2.0
# Login se imagem privada
echo "$GHCR_TOKEN" | docker login ghcr.io -u caiooliveirac --password-stdin

docker compose -f docker-compose.prod.yml pull
docker compose -f docker-compose.prod.yml up -d

docker compose -f docker-compose.prod.yml exec web python manage.py migrate
docker compose -f docker-compose.prod.yml exec web python manage.py seed_rules --fresh  # se precisar repovoar
```

## 10. Rollback
```
export APP_IMAGE=ghcr.io/caiooliveirac/samu-normas:<TAG_ANTIGA>
docker compose -f docker-compose.prod.yml up -d
```

## 11. Troubleshooting Rápido
Problema | Indício | Ação
---------|--------|------
`manifest unknown` | Pull falha | Tag não existe no registry – verificar build/push
`invalid token` | Push falha | Token sem `write:packages` ou expirado
`COPY ... not found` | Durante build | Contexto incorreto – usar `.` no diretório do Dockerfile
`Permission denied` (push) | Erro no final | Usando GITHUB_TOKEN fora do Actions – usar PAT
Frontend não atualiza | Assets antigos | Confirmar execução `npm run build` no stage frontend e cópia para `static/react`
Seed falha FK | IntegrityError | Ver se JSON precisa `<campo>_id` ou se ordem de criação foi alterada

## 12. Melhorias Futuras Sugeridas
- Workflow de build automático em push de tag (Actions) usando `docker/metadata-action`.
- Endpoint `/__version__` expondo: SHA, build date, app version.
- Tag de data sempre incluída (já suportada) para auditoria.
- Tornar imagem pública (se desejado) para eliminar necessidade de login em hosts de deploy read-only.
- Cache de build (usar `--cache-from` e `--cache-to=type=registry` no CI).
- Testes adicionais cobrindo comando de seed e consistência de contagem de objetos.
- Healthcheck HTTP explícito em Nginx ou no compose.

## 13. Endpoint de Versão (Proposta)
Adicionar em uma próxima iteração (exemplo):
```
# Em settings (build args passados via Dockerfile)
BUILD_SHA = os.getenv('BUILD_SHA')
APP_VERSION = os.getenv('APP_VERSION')
BUILD_DATE = os.getenv('BUILD_DATE')
```
View simples:
```
return JsonResponse({
  "sha": settings.BUILD_SHA,
  "version": settings.APP_VERSION,
  "build_date": settings.BUILD_DATE,
})
```

## 14. Segurança Básica
- Garantir `DEBUG=False` em produção.
- Configurar `SECURE_SSL_REDIRECT=True` e HSTS se estiver atrás de HTTPS.
- Rotacionar senhas do banco (script em `scripts/rotate_db_passwords.sh` se existir/ajustar).
- Manter SECRET_KEY fora do repositório (env ou secret manager).

## 15. Resumo Ultra Rápido (TL;DR)
1. `git pull` + editar código.
2. Rodar testes: `bash scripts/run_tests.sh`.
3. Criar tag: `git tag v0.X.Y && git push origin v0.X.Y`.
4. CI (ou local) builda e publica imagem.
5. Produção: `export APP_IMAGE=... && docker compose -f docker-compose.prod.yml up -d`.
6. `migrate` + `seed_rules` quando necessário.
7. Rollback = mudar tag e subir de novo.

---
Atualize este documento conforme novos fluxos forem introduzidos.
