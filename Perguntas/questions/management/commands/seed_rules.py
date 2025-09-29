import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.conf import settings

from questions.models import Rule, RuleCard, RuleBullet, Category, Tag

TABLE_ORDER = [  # dependentes primeiro para truncar com segurança depois
    'questions_rulebullet',
    'questions_rulecard',
    'questions_rule',
    'questions_category',
    'questions_tag',
]

MODEL_ORDER = [  # ordem de criação (menos dependentes primeiro)
    Category,
    Tag,
    Rule,
    RuleCard,
    RuleBullet,
]

DEFAULT_FIXTURE_NAME = 'rules_fixture.json'


class Command(BaseCommand):
    help = (
        "Importa/seed das regras a partir de um JSON (fixture simplificada).\n"
        "Também pode opcionalmente gerar backup SQL das tabelas e truncá-las antes.\n\n"
        "Uso básico:\n"
        "  python manage.py seed_rules --fixture rules_fixture.json\n\n"
        "Opções:\n"
        "  --fixture <path>   Caminho do JSON (default: rules_fixture.json na root do projeto).\n"
        "  --backup           Gera backup SQL das tabelas de regra.\n"
        "  --truncate         Trunca as tabelas antes de importar.\n"
        "  --dry-run          Valida o arquivo sem gravar no banco.\n"
    )

    def add_arguments(self, parser):
        parser.add_argument('--fixture', dest='fixture', default=DEFAULT_FIXTURE_NAME)
        parser.add_argument('--backup', action='store_true')
        parser.add_argument('--truncate', action='store_true')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        fixture_path = Path(options['fixture'])
        if not fixture_path.is_file():
            # tentar relativo ao BASE_DIR
            candidate = Path(settings.BASE_DIR) / fixture_path
            if candidate.is_file():
                fixture_path = candidate
            else:
                raise CommandError(f"Fixture não encontrada: {fixture_path}")

        self.stdout.write(self.style.NOTICE(f"Usando fixture: {fixture_path}"))

        try:
            data = json.loads(fixture_path.read_text(encoding='utf-8'))
        except Exception as e:
            raise CommandError(f"Erro lendo JSON: {e}")

        if not isinstance(data, list):
            raise CommandError("Fixture deve ser uma lista de objetos JSON exportados pelo dumpdata.")

        # Mapeia por model
        by_model = {}
        for obj in data:
            model_label = obj.get('model')
            if not model_label:
                raise CommandError('Objeto sem chave "model"')
            by_model.setdefault(model_label, []).append(obj)

        # Dry run: apenas estatísticas
        # Django converte '--dry-run' em chave 'dry_run'
        if options.get('dry_run'):
            self._print_stats(by_model)
            self.stdout.write(self.style.SUCCESS('Dry-run OK (nenhuma alteração aplicada).'))
            return

        if options['backup']:
            self._backup_tables()

        if options['truncate']:
            self._truncate_tables()

        # Import simples recriando objetos. Vamos usar a estrutura padrão do dumpdata
        with transaction.atomic():
            created_counts = {}
            for model_cls in MODEL_ORDER:
                label = f"questions.{model_cls.__name__.lower()}"
                objects = by_model.get(label, [])
                if not objects:
                    continue
                count = 0
                for raw in objects:
                    fields = raw.get('fields', {})
                    pk = raw.get('pk')
                    obj = model_cls(**fields)
                    # Se o dump tiver PK explícita e quisermos preservar:
                    if pk is not None:
                        obj.pk = pk
                    obj.save(force_insert=True)
                    count += 1
                created_counts[model_cls.__name__] = count

        for k, v in created_counts.items():
            self.stdout.write(self.style.SUCCESS(f"Criados {v} registros em {k}"))
        self.stdout.write(self.style.SUCCESS("Seed concluído."))

    # ---- utilitários ----
    def _print_stats(self, by_model):
        self.stdout.write("Resumo da fixture:")
        for model_label, objs in sorted(by_model.items()):
            self.stdout.write(f"  {model_label}: {len(objs)} registros")

    def _backup_tables(self):
        ts = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        outfile = Path(f"rules_backup_{ts}.sql")
        self.stdout.write(self.style.NOTICE(f"Gerando backup em {outfile} ..."))
        # Usa mysqldump se disponível. Se falhar, ignora com aviso.
        import shutil, subprocess
        mysqldump = shutil.which('mysqldump')
        if not mysqldump:
            self.stdout.write(self.style.WARNING('mysqldump não encontrado no PATH; pulando backup.'))
            return
        db_settings = settings.DATABASES['default']
        if 'mysql' not in db_settings['ENGINE']:
            self.stdout.write(self.style.WARNING('Banco não é MySQL/MariaDB; pulando backup mysqldump.'))
            return
        cmd = [
            mysqldump,
            f"-u{db_settings.get('USER','')}",
        ]
        password = db_settings.get('PASSWORD')
        if password:
            cmd.append(f"-p{password}")
        host = db_settings.get('HOST') or ''
        if host:
            cmd.append(f"-h{host}")
        port = db_settings.get('PORT') or ''
        if port:
            cmd.append(f"-P{port}")
        cmd.append(db_settings.get('NAME'))
        cmd.extend(TABLE_ORDER[::-1])  # ordem inversa só para leitura; não impacta
        try:
            with outfile.open('w', encoding='utf-8') as f:
                subprocess.check_call(cmd, stdout=f)
            self.stdout.write(self.style.SUCCESS(f"Backup criado: {outfile}"))
        except subprocess.CalledProcessError as e:
            self.stdout.write(self.style.WARNING(f"Falha ao gerar backup (code {e.returncode})."))

    def _truncate_tables(self):
        self.stdout.write(self.style.NOTICE("Truncando tabelas de regras..."))
        with connection.cursor() as cur:
            cur.execute('SET FOREIGN_KEY_CHECKS=0;')
            for table in TABLE_ORDER:  # primeiro dependentes
                cur.execute(f'TRUNCATE `{table}`;')
            cur.execute('SET FOREIGN_KEY_CHECKS=1;')
        self.stdout.write(self.style.SUCCESS("Truncate concluído."))
