# Deploy Produção – samu-normas

Este documento descreve fluxo de build, publicação e atualização da aplicação (Django + Gunicorn + Nginx + MariaDB + Frontend React/Vite).

## Quick Start (Resumo Ultra-Rápido)
Escolha UM dos fluxos abaixo:

| Cenário | O que fazer | Comando principal |
|---------|-------------|-------------------|
| Usar imagem já publicada pelo CI | Definir `APP_IMAGE` com tag imutável (sha curto) | `APP_IMAGE=ghcr.io/<owner>/<repo>/samu-normas:<sha> ./scripts/deploy.sh --force-recreate` |
| Testar local ou sem acesso ao registro | Build local da imagem | `./scripts/deploy.sh --build-local --force-recreate` |

Checks imediatos pós-subida:
```bash
curl -sf http://localhost/nginx-health && echo OK-NGINX
curl -sf http://localhost/healthz && echo OK-DJANGO
```
Se ambos OK, acesse via navegador (HTTP). Só depois habilite HTTPS.

## Atualizar só a estética (sem rebuild do container web)

### 1) Frontend React/Vite (rápido)
O `docker-compose.prod.yml` tem um serviço `frontend` que gera os assets do React em um volume dedicado (`react_volume`).
Isso evita rebuild da imagem `web` quando a mudança é só UI do frontend.

Comando:
```bash
./scripts/deploy.sh --frontend-only
```

Alternativa (sem script):
```bash
docker compose -f docker-compose.prod.yml run --rm frontend
```

### 2) Templates/CSS Django (rápido)
Para editar HTML/CSS das views Django sem rebuild da imagem `web`, use o override:
```bash
docker compose -f docker-compose.prod.yml -f docker-compose.prod.override.dev-templates.yml restart web
```
Esse override monta `templates/` e `static/` como volumes read-only dentro do container.

Para rollback rápido (imagem anterior):
```bash
export APP_IMAGE=ghcr.io/<owner>/<repo>/samu-normas:<sha_antigo>
./scripts/deploy.sh --force-recreate
```

## Visão Geral
- Backend: Django servido por Gunicorn no container `web`.
- Frontend: Build Vite incorporado na imagem (estágio Node). Arquivos finais em `static/react`.
- Banco: MariaDB (container `db`) com volume `db_data`.
- Proxy: Nginx servindo estáticos e proxy reverso para Gunicorn.
- Certificados: (opcional) via serviço `certbot` e volume `certs_volume`.

## Variáveis de Ambiente (arquivo `.env.prod`)
Obrigatórias / importantes:
- `SECRET_KEY` (ou `DJANGO_SECRET_KEY`)
- `DEBUG=False`
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_ROOT_PASSWORD`
- `ALLOWED_HOSTS` (inclua IP público e domínio)
- `CSRF_TRUSTED_ORIGINS` (inclua esquemas: `http://` e `https://` se usar TLS)
- `SECURE_SSL_REDIRECT` (True só após HTTPS funcional)
- `SECURE_HSTS_SECONDS` (ativar quando HTTPS estável; HSTS agressivo por default)

## Imagens Docker e APP_IMAGE
Em produção recomenda-se usar imagens imutáveis publicadas no GHCR (GitHub Container Registry). O workflow GitHub Actions publica tags:
- `latest`
- `<sha-curto>` (hash do commit)

Formato final da imagem: `ghcr.io/<owner>/<repo>/samu-normas:<tag>`.

### Fluxo Pull-Based
1. Merge no `master` dispara pipeline de build.
2. No servidor (EC2):
   ```bash
   export APP_IMAGE=ghcr.io/<owner>/<repo>/samu-normas:<sha>
   ./scripts/deploy.sh
   ```
3. Health automático verifica `/nginx-health` (Nginx) e `/healthz` (Django).

### Build Local (fallback)
Sem `APP_IMAGE` definido, o script faz build local usando `Dockerfile.prod`.

## Script de Deploy
Arquivo: `scripts/deploy.sh`
Principais flags:
- `--build-local` Força build local da imagem web.
- `--force-recreate` Recria containers (útil após alteração de environment).
- `--pull-only` Apenas faz pull da imagem, sem subir.
- `--health-url <URL>` Ajusta URL para health final.

Exemplos:
```bash
APP_IMAGE=ghcr.io/<owner>/<repo>/samu-normas:latest ./scripts/deploy.sh --force-recreate
./scripts/deploy.sh --build-local
```

## Health Endpoints
- Nginx: `/nginx-health` (retorna 200 sem tocar no Django)
- Django: `/healthz` (retorna plain text "ok")
 - Version: `/__version__` (JSON com sha, version, build_date)

## Inbox (perguntas enviadas) — acesso em produção
URL do painel de perguntas:
- `/inbox/` (requer usuário **staff**)

Fluxo típico:
1. Acesse `http(s)://SEU_HOST/inbox/`.
2. Se estiver deslogado, você será direcionado para uma tela de login.
   - Observação: como o `inbox` usa `staff_member_required`, o redirect pode cair em `/admin/login/?next=/inbox/`.
   - Se preferir usar a tela de login custom, faça login em `/login/` e depois volte para `/inbox/`.

### Criar usuário para o coordenador (recomendado)
Crie um usuário **staff** (não precisa ser superuser). Rode no servidor, na pasta `Perguntas/`:

1) Criar usuário (interativo):
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```
Durante a criação, marque como `Superuser` apenas se realmente precisar; para acessar `/inbox/` basta `Staff`.

2) Se o usuário já existe, defina/alterar senha:
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py changepassword NOME_DO_USUARIO
```

3) Ajustar permissões (staff) via Admin:
- Acesse `/admin/` → Users → selecione o usuário → marque **Staff status** → Save.

Dica operacional: envie a senha ao coordenador por canal seguro e, se possível, troque após o primeiro acesso.

## Checklists USA + Digest no Telegram

URLs úteis:
- Preenchimento do checklist: `/checklists/`
- Inbox de checklists (staff): `/inbox/checklists/`

Configuração (em `.env.prod`):
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_IDS` (lista separada por vírgula) ou `TELEGRAM_CHAT_ID` (único)

Envio do digest (manual):
- Pelo botão em `/inbox/checklists/` (após confirmação, envia com `force=1`)
- Via terminal:
   ```bash
   docker compose -f docker-compose.prod.yml exec web \
      python manage.py send_checklist_digest --slot manual --force
   ```

Mais detalhes do formato e funcionamento: `docs/CHECKLISTS_TELEGRAM.md`.

## HTTPS (Certbot)
Passo a passo seguro (não habilite redirect antes de ter certificado funcional):

1. Domínios: Decida o(s) domínio(s) (ex: `exemplo.com`, `www.exemplo.com`). Garanta DNS apontando para o IP da instância.
2. Ajuste `nginx/default.conf`: Descomente (ou adicione) o bloco `server` na porta 443 e substitua ocorrências de `SEU_DOMINIO` pelos domínios reais. Mantenha por ora `SECURE_SSL_REDIRECT=False` em `.env.prod` (evita loop antes de 443 responder).
3. Emissão STAGING (teste sem limite de rate):
   ```bash
   docker compose -f docker-compose.prod.yml run --rm certbot \
     certonly --webroot -w /var/www/certbot \
     -d exemplo.com -d www.exemplo.com \
     --email seu-email@dominio --agree-tos --no-eff-email --staging
   ```
4. Valide que os arquivos `fullchain.pem` e `privkey.pem` foram criados no volume `certs_volume` (caminho interno esperado em `/etc/letsencrypt/live/exemplo.com/`).
5. Teste local (abrir `https://exemplo.com` – navegador avisará que é staging / não confiável, o objetivo é validar fluxo de challenge).
6. Emissão PRODUÇÃO (remova `--staging`):
   ```bash
   docker compose -f docker-compose.prod.yml run --rm certbot \
     certonly --webroot -w /var/www/certbot \
     -d exemplo.com -d www.exemplo.com \
     --email seu-email@dominio --agree-tos --no-eff-email
   ```
7. Reinicie apenas o `nginx` (ele deve ler os certificados montados):
   ```bash
   docker compose -f docker-compose.prod.yml exec nginx nginx -s reload || \
   docker compose -f docker-compose.prod.yml restart nginx
   ```
8. Acesse `https://exemplo.com` e confirme cadeado válido.
9. Ative o redirect seguro: em `.env.prod` ajuste `SECURE_SSL_REDIRECT=True` e (opcional) `SECURE_HSTS_SECONDS=31536000` (HSTS forte). Recrie `web` para carregar a variável se necessário:
   ```bash
   ./scripts/deploy.sh --force-recreate
   ```
10. Atualize `CSRF_TRUSTED_ORIGINS` incluindo `https://exemplo.com` (e subdomínios). Sem isso, POSTs autenticados podem falhar.

Renovação automática (cron mensal / diário):
```cron
0 3 * * * cd /caminho/Perguntas && docker compose -f docker-compose.prod.yml run --rm certbot renew && docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

Notas:
- Se estiver atrás de um Load Balancer que termina TLS, talvez não precise do Certbot local; nesse caso mantenha `SECURE_SSL_REDIRECT=True` apenas se o LB encaminhar `X-Forwarded-Proto` corretamente.
- Em rate limits (erro 429) aguarde ou use staging para validação de config.

## Problemas Comuns & Soluções
| Sintoma | Causa provável | Ação |
|--------|----------------|------|
| Access denied MariaDB | Volume com senha antiga | `ALTER USER ... IDENTIFIED BY` ou recriar volume após set env_file no db |
| 301 forçando HTTPS sem cert | `SECURE_SSL_REDIRECT=True` ou Nginx redirect | Desativar em `.env.prod`, comentar bloco HTTPS |
| Página "Carregando…" | Build Vite ausente | Rebuild imagem (pipeline), verificar `static/react/assets/main-*.js` |
| Host inválido (400) | `ALLOWED_HOSTS` faltando | Adicionar IP/domínio e reiniciar `web` |
| Fallback de asset React | Manifest incompleto | Garantir `vite build` no estágio Node |
| Staticfiles vazio na 1ª subida | Volume nomeado `static_volume` montado sobrepõe conteúdo da imagem | Guard no entrypoint repovoa; verificar logs `[entrypoint] Guard:` ou remover volume e redeploy |

### ERRO RECORRENTE: Staticfiles Vazio / Assets Sumiram

Este é o problema que mais apareceu historicamente. Sintomas típicos:

- Página principal ou rota do frontend sem CSS/JS (console 404 para `/static/react/...`).
- Scoreboard carrega (porque é HTML inline), mas o restante do front parece "quebrado".
- Abrindo `http://HOST/static/react/index.html` retorna 404 ou arquivo muito pequeno.

#### Causa Raiz
Uso de volume nomeado `static_volume` montado em `/app/staticfiles`. Na primeira vez que o serviço `web` sobe com esse volume, o diretório do container (que tem os assets empacotados na imagem) é sobrescrito por um volume vazio. O processo normal deveria:
1. Rodar `collectstatic`.
2. Copiar/rsync de `static/` (onde o build Vite colocou assets) para `staticfiles/`.

Se `collectstatic` falha silenciosamente ou a cópia não ocorre, o Nginx serve uma pasta vazia, gerando 404.

#### Logs a observar
No container `web`:
```
[entrypoint] Coletando arquivos estáticos...
[entrypoint] Sincronizando assets Vite (static/ -> staticfiles/)
[entrypoint] Guard: staticfiles parece vazio (...)
```
O guard adicionado em outubro/2025 repopula automaticamente se detectar poucos arquivos (<10 por padrão) e loga:
```
[entrypoint] Guard: itens após repopular = X
```

#### Como Resolver (produção)
1. Verifique logs: `docker compose -f docker-compose.prod.yml logs -f web | grep -i entrypoint`.
2. Se não houver repopulação, execute manualmente dentro do container:
   ```bash
   docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput
   docker compose -f docker-compose.prod.yml exec web sh -c 'rsync -a static/ staticfiles/'
   ```
3. Teste um asset: `curl -I http://HOST/static/react/index.html` (esperado HTTP/1.1 200).
4. Se ainda vazio, remova o volume e redeploy:
   ```bash
   docker compose -f docker-compose.prod.yml down
   docker volume rm $(docker volume ls -q | grep static_volume)
   docker compose -f docker-compose.prod.yml up -d --build
   ```

#### Prevenção
- Confiar no guard (já ativo) — ele cobre maioria dos casos.
- Evitar editar manualmente `staticfiles/` dentro do container.
- Se não houver necessidade de persistir estáticos entre releases (a maioria dos casos), considerar remover o volume no futuro.

#### Verificação Rápida Pós-Deploy
```bash
curl -I http://HOST/static/react/index.html | head -n 5
docker compose -f docker-compose.prod.yml logs web | grep -i 'Guard:' | tail -n 3
```


## Checklist de Deploy (Humano ou Copilot)
1. `.env.prod` contém: SECRET_KEY forte, DEBUG=False, ALLOWED_HOSTS corretos, CSRF_TRUSTED_ORIGINS.
2. Se HTTPS: `SECURE_SSL_REDIRECT=True` e certs montados; caso contrário False.
3. `APP_IMAGE` definido (pull-based) OU decidir build local.
4. Executar `./scripts/deploy.sh --force-recreate` (se env mudou).
5. Verificar:
   - `docker compose ps` (db Healthy, web Up, nginx Up)
   - `curl -sf http://localhost/nginx-health`
   - `curl -sf http://localhost/healthz`
   - (Se HTTPS) `curl -Ik https://seu-dominio/ | grep -i strict-transport-security` (aparece somente após `SECURE_SSL_REDIRECT=True` e HSTS ativado)
6. Acessar aplicação via IP/domínio.
7. (Opcional) Criar superuser se ambiente novo.
8. (Opcional) Rodar smoke test:
```bash
ALLOW_SMOKE=1 ./scripts/smoke.sh --host http://localhost
```
Saída esperada: todos os blocos [OK] e restart web saudável em <= ~30s.

## Estrutura de Imagem
Camadas principais:
1. Construção de wheels Python (caching via Buildx/GHA).
2. Build frontend (Node 24) -> assets para `static/react`.
3. Instala runtime Python slim + copia assets + código.
4. Entrada via `scripts/entrypoint.prod.sh` (migrações + collectstatic + sync assets).

## Rollback
Tenha a tag anterior (sha antigo). Para reverter:
```bash
export APP_IMAGE=ghcr.io/<owner>/<repo>/samu-normas:<sha_antigo>
./scripts/deploy.sh --force-recreate
```

## Segurança / Hardening
- Ativar HSTS apenas após validar HTTPS.
- Rotacionar senhas do DB (script `scripts/rotate_db_passwords.sh` se existir futuro).
- Considerar adicionar Sentry para erros.

## Observabilidade futura (Sugestões)
- Adicionar logging estruturado Gunicorn.
- Adicionar métricas (Prometheus exporter / health extendido).

## Roadmap (Próximos Passos)
- Testes automáticos no workflow (pytest / flake8 / isort).
- Publicar SBOM (Syft) e scan de vulnerabilidades (Grype). 

## Testes Automatizados (Pytest)
Estrutura mínima adicionada:
- Arquivo `pytest.ini` configurando Django settings e filtros de warning.
- Dependências de desenvolvimento em `requirements-dev.txt` (não instaladas na imagem de produção).
- Teste exemplo em `tests/test_health.py` validando `/healthz`.
- Workflow GitHub Actions `tests.yml` executa pytest com `DB_ENGINE=sqlite` para velocidade.

Como rodar local (se tiver pip disponível):
```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest -q
```
Próximos incrementos sugeridos:
1. Adicionar testes para views críticas (`ask_view`, `api_search_log`).
2. Introduzir lint (flake8/ruff) e tipagem gradual (mypy) se necessário.
3. Teste de integração simples para endpoint React (`api_rules`).

Para configurar ambiente local sem sudo consulte `README_DEV.md`.

---
Gerado para reduzir tempo de próximas operações de deploy e dar contexto direto a ferramentas automatizadas.
