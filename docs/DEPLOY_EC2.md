# Deploy em EC2 (Opção A: Banco na mesma instância)

Este guia descreve o deploy na instância t4g.small (ARM64) com Docker Compose.

## 1. Pré-requisitos
- EC2 Ubuntu/Debian (ARM64) com portas 22 (SSH) e 8000 liberadas (temporário) ou detrás de um ALB.
- Usuário com sudo (ex: `ubuntu`).
- Domínio configurado (opcional nesta fase).

## 2. Instalar Docker e Compose
```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=arm64 signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/debian bookworm stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
# logout/login novamente
```

## 3. Obter código
Clone o repositório ou faça deploy do pacote:
```bash
git clone <repo-url> app && cd app
```

## 4. Criar arquivo de ambiente
Copiar modelo e editar:
```bash
cp .env.prod.example .env.prod
nano .env.prod  # Ajustar SECRET_KEY, ALLOWED_HOSTS, senhas
```
Gerar SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

## 5. Build local da imagem (na própria EC2)
```bash
docker compose -f docker-compose.prod.yml build --no-cache
```
Para acelerar builds futuros: `--build` apenas quando alterar código.

## 6. Subir stack
```bash
docker compose -f docker-compose.prod.yml up -d
```
Verificar:
```bash
docker compose -f docker-compose.prod.yml ps
docker logs -f $(docker compose -f docker-compose.prod.yml ps -q web)
```

## 7. Criar superusuário
```bash
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

## 8. Testar acesso
No navegador: `http://IP_PUBLICO:8000/`

## 9. Logs e troubleshooting
- Logs app: `docker compose -f docker-compose.prod.yml logs -f web`
- Logs DB: `docker compose -f docker-compose.prod.yml logs -f db`
- Health DB: `docker exec -it $(docker compose -f docker-compose.prod.yml ps -q db) mysql -u$DB_USER -p$DB_PASSWORD $DB_NAME -e 'SELECT 1;'`

## 10. Atualizações de código
Pull novo código e rebuild:
```bash
git pull
docker compose -f docker-compose.prod.yml build web
docker compose -f docker-compose.prod.yml up -d
```
Migrações já rodam automaticamente via entrypoint.

## 11. Atualizações de dependências
```bash
docker compose -f docker-compose.prod.yml build --no-cache web
```

## 12. Backup do banco
Simples (dump manual):
```bash
mkdir -p backups
DATE=$(date +%Y%m%d_%H%M%S)
docker compose -f docker-compose.prod.yml exec db mysqldump -u$DB_USER -p$DB_PASSWORD $DB_NAME > backups/dump_$DATE.sql
```
Automatizar: cron ou systemd timer apontando para script similar.

## 13. Harden/Produção futura
- Colocar Nginx ou ALB em frente (SSL / gzip / headers de segurança).
- Mover banco para RDS quando precisar de snapshots automáticos.
- Configurar CloudWatch (ou Loki/Promtail) para logs centralizados.
- Monitorar com health endpoint (se criar) ou `manage.py check` periódico.

## 14. Limpeza de imagens antigas
```bash
docker image prune -f
```

## 15. Rollback rápido
- Mantenha tag anterior (ex: `:prev`).
- Para voltar: `docker compose -f docker-compose.prod.yml pull web && docker compose -f docker-compose.prod.yml up -d web` apontando para tag anterior.

## 16. Segurança
- Não deixe `.env.prod` versionado nem world-readable (`chmod 600`).
- Use senha forte no DB mesmo local.
- Ative firewall/SG para restringir acesso à porta 8000 quando tiver proxy.

---
Pronto: ambiente de produção básico operacional na mesma EC2.
