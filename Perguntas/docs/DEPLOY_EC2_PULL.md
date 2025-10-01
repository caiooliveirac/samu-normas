# Deploy Pull-Based em EC2 (GHCR)

Este guia descreve como realizar deploy da aplicação usando imagens publicadas no GitHub Container Registry (GHCR) sem build no servidor.

## 1. Pré-requisitos na EC2
- Ubuntu/Debian atualizado
- Docker + Docker Compose Plugin instalados
- Usuário no grupo `docker` (logout/login após adicionar)
- Arquivo `.env.prod` com variáveis necessárias (DB senhas, DEBUG=False, SECRET_KEY etc.)

Instalação Docker (referência rápida):
```
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker $USER
```
Depois: logout/login no SSH.

## 2. Login no GHCR
Se o repositório for público: apenas pull (anon) deve funcionar. Caso contrário gerar Personal Access Token (PAT) com `read:packages`.
```
echo "<TOKEN>" | docker login ghcr.io -u <SEU_USUARIO> --password-stdin
```

## 3. Clonar o repositório (para ter docker-compose e scripts)
```
git clone https://github.com/caiooliveirac/samu-normas.git
cd samu-normas
```
Opcional: manter apenas `docker-compose.prod.yml`, `scripts/`, `.env.prod` em um diretório infra separado.

## 4. Definir tag da imagem
Tags disponíveis (exemplos):
- `latest` (último build da master)
- `master` (alias fixo da branch principal)
- `ts-YYYYMMDD-HHMM` (timestamp)
- `<sha_curt>` (imutável)
- `vX.Y.Z` (release)

Listar manifest (ex local):
```
docker pull ghcr.io/caiooliveirac/samu-normas:latest
```

## 5. Arquivo `.env.prod`
Exemplo mínimo:
```
DEBUG=False
SECRET_KEY=alterar
DB_NAME=samu_q
DB_USER=samu_q
DB_PASSWORD=senha-app
DB_HOST=db
DB_PORT=3306
DB_ROOT_PASSWORD=senha-root
ALLOWED_HOSTS=seu.dominio,localhost
CSRF_TRUSTED_ORIGINS=https://seu.dominio
```

## 6. Executar deploy
```
APP_TAG=master ./scripts/deploy_pull.sh
```
Flags úteis:
- `FORCE_RECREATE=1` força recriação dos containers
- `NO_MIGRATE=1` pula migrations
- `NO_COLLECTSTATIC=1` pula collectstatic (caso a imagem já tenha staticfiles — multi-stage com collect inside future)
- `APP_TAG=<sha>` garante rollback / imutabilidade

## 7. Atualizar versão (rolling simples)
Basta rodar novamente com APP_TAG novo. O compose faz update da imagem.
```
APP_TAG=<novo_sha> ./scripts/deploy_pull.sh
```

## 8. Rollback rápido
```
APP_TAG=<sha_antigo> ./scripts/deploy_pull.sh
```

## 9. Logs e troubleshooting
```
docker compose -f docker-compose.prod.yml logs -f web
```
Checar DB saúde:
```
docker compose -f docker-compose.prod.yml exec db mariadb -uroot -p$DB_ROOT_PASSWORD -e 'SHOW DATABASES;' 
```

## 10. HTTPS
Após apontar DNS do domínio para o IP da EC2 e ajustar `nginx/default.conf`, emitir certificado:
```
docker compose -f docker-compose.prod.yml run --rm certbot certonly --webroot -w /var/www/certbot -d seu.dominio --email voce@exemplo.com --agree-tos --no-eff-email
```
Depois reiniciar nginx:
```
docker compose -f docker-compose.prod.yml restart nginx
```

## 11. Segurança adicional
- Restrinja acesso SSH (fail2ban, ufw)
- Rotacione senhas DB periodicamente (`scripts/rotate_db_passwords.sh` se existir)
- Configure backups do volume `db_data`

## 12. Próximos aprimoramentos
- Pipeline para publicar SBOM / assinatura (cosign)
- Healthcheck externo + monitoração
- Deploy canário (duas pilhas compose)

---
Documentação gerada automaticamente para suporte ao deploy pull-based.
