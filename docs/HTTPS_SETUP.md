# Guia de Ativação de HTTPS

Este documento descreve como ativar HTTPS usando Nginx + Certbot dentro do docker-compose de produção.

## Visão Geral

Componentes:
- Nginx (agora com blocos `server` para 80 -> redirect e 443 com TLS)
- Serviço opcional `certbot` para emissão/renovação
- Volume `certs_volume` montado em `/certs` no Nginx e `/etc/letsencrypt` no Certbot
- Django configurado para cookies seguros e HSTS quando `DEBUG=False`

Alternativa: Terminar TLS em um Load Balancer (AWS ALB/NLB) e deixar Nginx somente HTTP interno (simplifica certificados, mas depende de infra externa). Se seguir essa rota, remova o redirect e bloco 443.

## Pré-Requisitos
1. Domínio apontando (DNS A/AAAA) para o IP público do servidor
2. Portas 80 (e depois 443) liberadas no security group/firewall
3. docker-compose de produção atualizado (já com `certs_volume` e novo `default.conf`)
4. Variáveis de ambiente ajustadas: `DEBUG=False`, `ALLOWED_HOSTS=seu.dominio`

## Passo a Passo (Emissão Inicial)

1. Subir stack sem HTTPS final ainda (vai responder na porta 80):
```
docker compose -f docker-compose.prod.yml up -d nginx web db
```

2. (Opcional, STAGING) Testar emissão staging para evitar rate limit:
```
./scripts/certbot_helper.sh issue exemplo.com seu-email@exemplo.com
```
   - Verifique saída. Certificados de staging NÃO são confiáveis (cadeia diferente).

3. Emissão produção real:
```
./scripts/certbot_helper.sh issue-prod exemplo.com seu-email@exemplo.com
```
   - Após sucesso, os arquivos ficarão em `certs_volume` (host: volume docker; container Nginx: `/certs/live/exemplo.com/`).

4. Editar `nginx/default.conf` substituindo `SEU_DOMINIO` por `exemplo.com` (e adicionar `www.exemplo.com` se aplicável em `server_name`).

5. Reiniciar Nginx:
```
docker compose -f docker-compose.prod.yml restart nginx
```

6. Conferir:
```
 curl -I https://exemplo.com
```
   - Verificar status 200/301, cabeçalhos HSTS, certificados válidos (em browser ou `openssl s_client -connect exemplo.com:443`).

## Renovação
Certificados Let’s Encrypt duram 90 dias. Faça um cron mensal (ex: dia 1) executando:
```
0 3 1 * * /usr/bin/docker compose -f /caminho/docker-compose.prod.yml run --rm certbot renew --quiet && /usr/bin/docker compose -f /caminho/docker-compose.prod.yml exec nginx nginx -s reload
```
Teste antes com:
```
./scripts/certbot_helper.sh test-renew
```

## Ajustes Django
As flags já foram adicionadas em `settings.py` para ativar segurança quando `DEBUG=False`:
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_HSTS_SECONDS=63072000` (pode reduzir para 300 no primeiro deploy antes de aumentar)
- `SECURE_HSTS_PRELOAD=True` e `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`

Se precisar reduzir HSTS temporariamente, defina em `.env.prod`:
```
SECURE_HSTS_SECONDS=300
```

## Multi-domínio / SAN
Para incluir www e raiz:
```
./scripts/certbot_helper.sh issue-prod exemplo.com seu-email@exemplo.com
# Depois repetir com -d www.exemplo.com OU usar: certonly --standalone -d exemplo.com -d www.exemplo.com
```
Ajustar `server_name`:
```
server_name exemplo.com www.exemplo.com;
```

## Rollback / Problemas
- Se HTTPS falhar, pode comentar bloco 443 e remover redirect para voltar a HTTP enquanto depura.
- Erros comuns:
  - `Invalid response from http://exemplo.com/.well-known/...` → Porta 80 não acessível ou DNS não propagado.
  - Rate limit: usar staging primeiro.

## TLS via Load Balancer (Alternativa)
Se usar ALB:
- Remover bloco 443 e redirect 80->443
- Deixar `proxy_set_header X-Forwarded-Proto $scheme;` (ALB envia `https` no header)
- Manter flags Django de segurança (ainda funcionarão com `SECURE_PROXY_SSL_HEADER`)
- Certificados e renovação passam a ser responsabilidade do ALB

## Checklist Final Produção
- [ ] DNS propagado (ping/domínio resolve)
- [ ] Emissão staging testada
- [ ] Certificado produção emitido
- [ ] `default.conf` atualizado com domínio
- [ ] Nginx reiniciado
- [ ] HSTS testado (`curl -I` mostra Strict-Transport-Security)
- [ ] Cron de renovação configurado
- [ ] Navegador sem aviso de segurança

## Próximas Melhorias
- CSP (Content-Security-Policy) restritiva após mapear assets.
- Rate limiting /login e /admin com `limit_req`.
- OCSP stapling (exige `ssl_stapling on;` e cadeias adequadas).
- Logs JSON estruturados (facilita observabilidade).

---

Dúvidas ou erros: verificar logs do container certbot ou `docker compose logs nginx`.
