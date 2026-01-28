# Deploy Pull-Based (Imagem Prebuild)

Este guia descreve como usar a imagem publicada no GHCR em vez de fazer build na EC2.

## Pipeline
- Workflow: `.github/workflows/build-and-push.yml`
- Gatilhos: push em `master` e tags `v*`
- Publica multi-arch: `ghcr.io/caiooliveirac/samu-normas:latest`, `:SHA_CURTO`, e se tag existir `:vX.Y.Z`

## Pré-requisitos (Servidor EC2)
1. Docker e plugin compose instalados
2. Criar/ajustar `.env.prod` (como já documentado)
3. Login no GHCR com token de leitura (se o repositório/imagem for privado)

Login (se privado):
```bash
docker login ghcr.io -u <seu-usuario> -p <TOKEN_COM_read:packages>
```
Se público, não precisa de login para apenas pull.

## Atualizando para nova versão
No diretório do compose (`docker-compose.prod.yml`):
```bash
export APP_IMAGE=ghcr.io/caiooliveirac/samu-normas:latest
# Puxar imagem mais recente
docker compose -f docker-compose.prod.yml pull web
# Atualizar containers (sem rebuild)
docker compose -f docker-compose.prod.yml up -d web
```

Para usar uma tag específica (imutável):
```bash
export APP_IMAGE=ghcr.io/caiooliveirac/samu-normas:<SHA_CURTO>
```
Ou release:
```bash
export APP_IMAGE=ghcr.io/caiooliveirac/samu-normas:v1.0.0
```

## Rollback
Se algo quebrar na `latest`, troque APP_IMAGE para um SHA anterior que você sabe que funcionava e repita pull + up.

## Limpando imagens antigas
```bash
docker image prune -f
```

## Adicionando ao systemd (opcional)
Crie: `/etc/systemd/system/samu-normas.service`
```ini
[Unit]
Description=Samu Normas (Pull Based Deploy)
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/opt/samu-normas/app
Environment=APP_IMAGE=ghcr.io/caiooliveirac/samu-normas:latest
ExecStart=/usr/bin/docker compose -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.prod.yml down
RemainAfterExit=yes
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```
Ativar:
```bash
sudo systemctl daemon-reload
sudo systemctl enable samu-normas
sudo systemctl start samu-normas
```

## Boas Práticas Futuras
- Adicionar testes antes do build (pytest) no workflow
- Assinar imagens (cosign) para integridade
- Renovar dependências com segurança (pip-audit) como job separado
- Observar logs (json) centralizados

## Checklist Rápido
- [ ] Workflow rodou e publicou imagem
- [ ] APP_IMAGE exportado na EC2
- [ ] docker compose pull web OK
- [ ] up -d aplicado sem rebuild
- [ ] Versão validada (curl /, /admin)
- [ ] Registrar SHA usado para rollback
