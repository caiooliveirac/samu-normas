## Testes do Projeto

### Camadas de Teste
- Smoke (já incluso): verifica home e admin redirect.
- Futuro: testes de modelos, views específicas e comandos management.

### Opções de Banco nos Testes
1. SQLite (rápido, usado na CI):
   ```bash
   DB_ENGINE=sqlite python manage.py test
   ```
2. MariaDB real via docker-compose (recomendado para detectar diferenças de SQL):
   ```bash
   export DB_ROOT_PASSWORD=<root_atual>
   ./scripts/test_mariadb.sh
   ```

### Variáveis relevantes
| Variável | Função |
|----------|--------|
| DB_ENGINE | Define backend (mysql ou sqlite) |
| DB_NAME | Banco principal (default samu_q) |
| DB_TEST_NAME | Banco usado nos testes (default <DB_NAME>_test) |
| DB_ROOT_PASSWORD | Necessário para garantir criação/grants do banco de teste |

### Como funciona `test_mariadb.sh`
1. Sobe serviços `db` e `web` (compose).
2. Aguarda saúde do banco.
3. Cria database de teste se não existir e aplica GRANT ao usuário de aplicação.
4. Executa `manage.py test` dentro do container `web` com `DB_ENGINE=mysql` e `DB_TEST_NAME`.

### Criar banco de teste manualmente (alternativa)
```bash
docker compose -f docker-compose.prod.yml exec db mariadb -uroot -p"$DB_ROOT_PASSWORD" -e "CREATE DATABASE IF NOT EXISTS samu_q_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; GRANT ALL PRIVILEGES ON samu_q_test.* TO 'samu_q'@'%'; FLUSH PRIVILEGES;"
```

### Mantendo banco de teste entre execuções
Use:
```bash
docker compose -f docker-compose.prod.yml exec -e DB_ENGINE=mysql -e DB_TEST_NAME=samu_q_test web python manage.py test --keepdb
```

### Recomendações Futuras
- Adicionar marcações (pytest + django) se a suíte crescer.
- Separar testes de integração (tocam banco real) de unit tests (mock). 
- Pipeline adicional semanal rodando contra MariaDB real (serviço extra no workflow). 
