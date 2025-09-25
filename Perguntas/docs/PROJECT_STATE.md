# Projeto SAMU — Estado Atual (snapshot)

## Infra
- **EC2 Ubuntu** + **Nginx** proxy → **Gunicorn** em `127.0.0.1:8000`
- **Django 5.2.6**, Python 3.12 (venv em `./.venv`)
- **Static**: `STATIC_ROOT=/opt/samu-normas/Perguntas/staticfiles` (Nginx: `location /static/ { alias ... }`)
- **DEBUG**: atualmente **True** (trocar para False após ajustes)
- **Banco**: **SQLite** (planejado migrar para MySQL/MariaDB)

## Código (paths-chave)
- Projeto: `/opt/samu-normas/Perguntas`
- App principal: `questions`
- CSS global: `static/css/ask.css` (aplicado em todas as páginas)
- Templates:
  - `questions/templates/questions/home.html` (/** */)
  - `questions/templates/questions/ask.html` (/ask)
  - `questions/templates/questions/inbox.html` (/inbox)
  - `questions/templates/questions/inbox_detail.html` (/inbox/<id>)
  - `templates/registration/login.html` (/login)
- URLs:
  - `samu_q/urls.py` → inclui `questions.urls`, login/logout, `/healthz`
  - `questions/urls.py` → `''->home`, `ask/`, `inbox/`, etc.

## Funcionalidades
- **/ (Home)**: lista `Rule` (FAQ) com busca client-side e botão **Perguntar**
- **/ask**: formulário anônimo salva `Question` (hash de IP)
- **/login**: tela de login custom (usa `ask.css`)
- **/inbox**: painel simples (staff), filtra/abre/“marcar revisada”, exporta CSV

## Modelos
- `Question(text, category, created_at, status[new/reviewed], ip_hash)`
- `Rule(title, slug, category, body, is_published, order, created_at, updated_at)`
- Admin: `Question` e `Rule` registrados

## Deploy / Serviço
- systemd: `/etc/systemd/system/perguntas.service`
  - ExecStart: `gunicorn samu_q.wsgi:application --bind 127.0.0.1:8000 --workers 3`
- Nginx: `/etc/nginx/sites-available/perguntas` (default_server, proxy para 127.0.0.1:8000)

## Próximos passos desejados
1) **Estética**: refinar layout (grid da home, tipografia, headers fixos, paginação).
2) **FAQ**: detalhar por **/regra/<slug>**, categorias e ordenação.
3) **DB**: migrar de **SQLite → MySQL/MariaDB** (com `mysqlclient` e dump/load).
4) **Produção**: `DEBUG=False`, `ALLOWED_HOSTS` certinho, HTTPS (Certbot), logs.
5) **Qualidade**: script de deploy pronto (já existe `~/deploy_perguntas.sh`), healthcheck OK.

## Como me “passar o contexto” numa conversa nova
Abra o arquivo e **cole o conteúdo** deste `PROJECT_STATE.md` na primeira mensagem da nova conversa.  
Se preferir, rode o script abaixo e cole a saída (tem versões e checks).

