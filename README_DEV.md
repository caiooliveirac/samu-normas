# Guia Rápido de Desenvolvimento (Atualizado)

> Nova documentação consolidada detalhada disponível em `docs/DEV_GUIDE.md`. Este arquivo mantém o resumo essencial. Para fluxo completo (build, seed, deploy, rollback, troubleshooting), consulte o guia.

## Ambiente de Desenvolvimento

Este guia descreve três abordagens para trabalhar localmente.

### Opção 1 – Desenvolvimento desacoplado (Docker) (recomendado)
Você pode rodar **backend**, **frontend** e **db** de forma independente (ou tudo junto), sem rebuild a cada mudança de código.

Variáveis principais:
- `DEV_BACKEND_PORT` (padrão `8000`) → host para o Django (container `:8000`)
- `DEV_FRONTEND_PORT` (padrão `5173`) → host para o Vite
- `VITE_PROXY_TARGET` → para o frontend encaminhar chamadas `GET /api/...` para o backend

#### Backend + DB (sem frontend)
1) Suba `backend` + `db`:
```bash
docker compose -p perguntas-dev -f docker-compose.dev.yml up -d backend
```

2) Acesse:
- App Django: `http://localhost:8001/`

#### Frontend (Vite) sozinho
1) Suba apenas o Vite (sem backend):
```bash
docker compose -p perguntas-frontend -f docker-compose.frontend.dev.yml up -d
```

2) Acesse:
- Vite: `http://localhost:5173/`

Opcional (integrar com API): rode o backend em outro compose e aponte proxy:
```bash
VITE_PROXY_TARGET=http://localhost:8001 docker compose -p perguntas-frontend -f docker-compose.frontend.dev.yml up -d --force-recreate
```

#### Tudo integrado (DB + backend + frontend)
```bash
docker compose -p perguntas-dev -f docker-compose.dev.full.yml up -d
```

A UI vai chamar `http://localhost:5173/api/...` e o Vite proxy encaminha para o backend.

Se a tela estiver “vazia” (sem cards), normalmente é porque o banco do dev ainda está vazio. Rode o seed uma vez:
```bash
docker compose -p perguntas-dev -f docker-compose.dev.full.yml exec backend \
	python manage.py seed_rules --fixture rules_seed.json --fresh
```

#### Recomendado (mais rápido): DB separado sempre up + app sobe/desce sem derrubar o banco
Isso reduz o tempo a cada teste porque você não reinicializa o MariaDB.

Nota importante (para não reconstruir tudo):
- Alterações em `frontend/src/**` entram por volume e o Vite faz HMR. Você **não** precisa `--build`.
- Alterações no backend Python também entram por volume; o `runserver` recarrega.
- Só use `docker compose ... build` quando mudar dependências (ex.: `requirements.txt` ou `frontend/package-lock.json`).

1) Suba o banco (uma vez) e deixe rodando:
```bash
docker compose -p perguntas-dev -f docker-compose.dev.db.yml up -d
```

2) Suba a aplicação (backend+frontend) quando for trabalhar:
```bash
docker compose -p perguntas-dev -f docker-compose.dev.app.yml up -d
```

Para abrir o app pelo Django (`http://localhost:8000/`) e ver o React em dev, você precisa que o navegador consiga acessar o Vite também.
No VS Code Remote SSH, encaminhe **as duas portas**: `8000` (Django) e `5173` (Vite).

Se o VS Code mapear a porta remota do Vite para outra porta local, defina `VITE_DEV_SERVER` ao subir o backend:
```bash
VITE_DEV_SERVER=http://localhost:5173 docker compose -p perguntas-dev -f docker-compose.dev.app.yml up -d
```

Se quiser (re)subir apenas um serviço sem mexer no outro:
```bash
docker compose -p perguntas-dev -f docker-compose.dev.app.yml up -d --no-deps frontend
docker compose -p perguntas-dev -f docker-compose.dev.app.yml up -d --no-deps backend
```

3) Popule o banco (apenas na primeira vez, ou se você apagar o volume):
```bash
docker compose -p perguntas-dev -f docker-compose.dev.app.yml exec backend \
	python manage.py seed_rules --fixture rules_seed.json --fresh
```

4) Para parar só a app (mantendo o DB de pé):
```bash
docker compose -p perguntas-dev -f docker-compose.dev.app.yml stop
```

#### Acesso via EC2/SSH (Port Forward)
Se você está desenvolvendo num servidor remoto (ex.: EC2), exponha apenas em `127.0.0.1` no servidor e use túnel:

1) Suba o stack (exemplo integrado):
```bash
DEV_BACKEND_PORT=8001 DEV_FRONTEND_PORT=5173 docker compose -p perguntas-dev -f docker-compose.dev.full.yml up -d
```

2) No seu computador local, abra um túnel SSH:
```bash
ssh -L 8001:localhost:8001 -L 5173:localhost:5173 ubuntu@SEU_HOST
```

Se você estiver usando outras portas no servidor (ex.: `8002` e `5174`):
```bash
ssh -L 8002:localhost:8002 -L 5174:localhost:5174 ubuntu@SEU_HOST
```

Alternativa (mais simples no VS Code Remote SSH):
- Abra a aba **Ports** (Portas) no VS Code
- Clique em **Forward a Port**
- Adicione as portas que você escolheu no servidor (ex.: `8002` e `5174`)
- No Mac, acesse `http://localhost:8002/` (Django) e `http://localhost:5174/` (Vite)

Observação importante: às vezes o VS Code encaminha a porta remota para uma **porta local diferente**.
Se o Django estiver tentando carregar `http://localhost:5174/...` mas no seu Mac o Vite ficou em outra porta (ex.: `http://localhost:5173`), suba o stack definindo explicitamente:
```bash
VITE_DEV_SERVER=http://localhost:5173 DEV_BACKEND_PORT=8002 DEV_FRONTEND_PORT=5174 \
	docker compose -p perguntas-dev -f docker-compose.dev.full.yml up -d
```

3) Acesse no navegador:
- Backend: `http://localhost:8001/`
- Frontend: `http://localhost:5173/`

Se você mudou as portas no servidor (ex.: `DEV_BACKEND_PORT=8002` e `DEV_FRONTEND_PORT=5174`), o `VITE_DEV_SERVER` e o HMR já acompanham automaticamente (quando você usa os compose deste repositório).

Riscos e escopo:
- Usuários finais não veem suas mudanças de dev se usarem o ambiente de produção (DEBUG=0). HMR só roda quando DEBUG=1 e o desenvolvedor está servindo o Vite localmente.
- Evite habilitar DEBUG/HMR em produção. Não exponha a porta 5173 publicamente.

### Opção 2 – Virtualenv local (sem sudo)
Script: `scripts/setup_venv.sh`

Cria `.venv/` mesmo em sistemas onde `python3-venv` ou `pip` não estão pré-instalados.

Passos:
```bash
./scripts/setup_venv.sh dev
source .venv/bin/activate
pytest -q
```
Somente base (sem dev deps):
```bash
./scripts/setup_venv.sh
```

Recriar do zero:
```bash
rm -rf .venv
./scripts/setup_venv.sh dev
```

### Opção 3 – Docker para shell de desenvolvimento
Para espelhar a imagem:
```bash
docker compose -f Perguntas/docker-compose.prod.yml run --rm web bash
```
Dentro do container:
```bash
python manage.py shell
python manage.py migrate --plan
pytest  # se instalar dev deps manualmente
```

## Build de assets para produção
Quando for publicar sem HMR:
```bash
cd frontend
npm run build
```
Isso gera assets em `static/react/` e o Django servirá via manifest com `DEBUG=0`.

## Dicas
- Adicione `/.venv` ao `.gitignore` se ainda não estiver.
- Evite commitar dependências compiladas em `site-packages`.
- Use `pip freeze > requirements-lock.txt` para snapshot reprodutível.

## Comandos úteis
```bash
# Backend dev (Django com DEBUG=1)
docker compose -f docker-compose.dev.yml up -d backend
docker compose -f docker-compose.dev.yml logs -f backend

# Vite HMR
docker compose -f docker-compose.frontend.dev.yml up -d

# Build produção
cd frontend && npm run build
```
