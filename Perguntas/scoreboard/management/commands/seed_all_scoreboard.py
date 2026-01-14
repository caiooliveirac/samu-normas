from django.core.management.base import BaseCommand, CommandError
from django.core import management

class Command(BaseCommand):
    help = "Roda todos os seeds do scoreboard (faculdades, modalidades e resultados iniciais). Idempotente."

    def add_arguments(self, parser):
        parser.add_argument('--force-results', action='store_true', help='Força atualizar pontos customizados dos resultados iniciais.')

    def handle(self, *args, **options):
        force = options['force_results']
        try:
            management.call_command('seed_faculties')
            management.call_command('seed_modalities')
            if force:
                management.call_command('seed_initial_results', '--force')
            else:
                management.call_command('seed_initial_results')
        except CommandError as e:
            raise e
        self.stdout.write(self.style.SUCCESS('Seeds scoreboard concluídos.'))
