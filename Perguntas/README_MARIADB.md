# Migração para MariaDB/MySQL

Este projeto Django (pasta `Perguntas/`) estava usando SQLite e agora suporta MariaDB/MySQL por variáveis de ambiente. A configuração padrão usa MariaDB.

## 1) Dependências

- `mysqlclient` (já listado em `requirements.txt`)
- Servidor MariaDB 10.5+ (ou MySQL 8+)

No macOS (Homebrew):

- Instalar MariaDB: `brew install mariadb`
- Iniciar serviço: `brew services start mariadb`

Em EC2 (Amazon Linux/Ubuntu):
- Instale `mariadb-server` via `yum` ou `apt` e habilite o serviço.

## 2) Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste:

```
DJANGO_SECRET_KEY=... 
DJANGO_DEBUG=False
ALLOWED_HOSTS=seu.dominio,IP

DB_ENGINE=mysql
DB_NAME=samu_q
DB_USER=samu_q
DB_PASSWORD=super-secret
DB_HOST=127.0.0.1
DB_PORT=3306
DB_CONN_MAX_AGE=60
DB_ATOMIC_REQUESTS=True
```

Em desenvolvimento local sem MariaDB, defina `DB_ENGINE=sqlite` para continuar usando `db.sqlite3`.

## 3) Criar banco e usuário

No MariaDB:

```sql
CREATE DATABASE samu_q CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'samu_q'@'%' IDENTIFIED BY 'super-secret';
GRANT ALL PRIVILEGES ON samu_q.* TO 'samu_q'@'%';
FLUSH PRIVILEGES;
```

Para acesso apenas local na EC2:

```sql
CREATE USER 'samu_q'@'localhost' IDENTIFIED BY 'super-secret';
GRANT ALL PRIVILEGES ON samu_q.* TO 'samu_q'@'localhost';
FLUSH PRIVILEGES;
```

## 4) Migrar dados do SQLite (opcional)

Se quiser levar dados do `db.sqlite3` para MariaDB:

1. Gere um dump JSON:
   ```bash
   python manage.py dumpdata --natural-primary --natural-foreign --indent 2 > dump.json
   ```
2. Ajuste `.env` para apontar para MariaDB (DB_ENGINE=mysql) e aplique migrações:
   ```bash
   python manage.py migrate
   ```
3. Carregue os dados:
   ```bash
   python manage.py loaddata dump.json
   ```

## 5) Aplicar migrações

Com `.env` configurado para MariaDB:

```bash
python manage.py migrate
```

## 6) Checagem e superusuário

```bash
python manage.py check
python manage.py createsuperuser
```

## Notas de produção (EC2 t4g.micro)

- Use `gunicorn` + `nginx` com `Unix socket`.
- Defina `DEBUG=False` e `ALLOWED_HOSTS`.
- Configure backups do banco (mysqldump) e `logrotate`.
- Ative `ufw`/Security Group liberando só 80/443 e 22.
- Use `CONN_MAX_AGE` > 0 para manter conexões.
- Para ARM (t4g), `mysqlclient` compila via `build-essential`/`python3-dev` (instale antes de `pip install -r requirements.txt`).
