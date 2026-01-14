# Guia Rápido de Desenvolvimento (Atualizado)

> Nova documentação consolidada detalhada disponível em `docs/DEV_GUIDE.md`. Este arquivo mantém o resumo essencial. Para fluxo completo (build, seed, deploy, rollback, troubleshooting), consulte o guia.

## Ambiente de Desenvolvimento

Este guia descreve três abordagens para trabalhar localmente.

### Opção 1 – Vite com Hot Reload (HMR) + Django dev (recomendado para UI)
Fluxo rápido sem rebuild de imagem a cada mudança de CSS/JS/HTML.

1) Suba o backend com Compose de dev (monta volume e usa `DEBUG=1`):
```bash
docker compose -f docker-compose.dev.yml up -d web
```

2) Rode o Vite dev server (HMR):
```bash
cd frontend
npm install
npm run dev
```

3) Acesse o app (ex.: http://localhost:8000/scoreboard/). Os templates detectarão HMR e carregarão assets via `http://localhost:5173` automaticamente.

Variáveis:
- `DEBUG=1` (no web dev) habilita HMR; `VITE_DEV=0` força usar assets buildados mesmo em debug.
- `VITE_DEV_SERVER` define a URL do dev server (padrão `http://localhost:5173`).

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
docker compose -f docker-compose.dev.yml up -d web
docker compose -f docker-compose.dev.yml logs -f web

# Vite HMR
cd frontend && npm run dev

# Build produção
cd frontend && npm run build
```
