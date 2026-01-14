from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from scoreboard.models import Faculty, Modality, Result

POKER_RESULTS = [
    ("UNIFG GUANAMBI", 20),
    ("AFYA SSA", 13),
    ("INDOMED ALAGOINHAS", 9),
    ("UNEX FSA", 6),
    ("ZARNS", 4),
    ("UFRB", 3),
    ("ESTÁCIO JUAZEIRO", 2),
    ("UESB JEQUIÉ", 1),
]

XADREZ_RESULTS = [
    ("UNIFACS", 20),
    ("BAHIANA", 13),
    ("UFBA", 9),
    ("ZARNS", 6),
    ("UFRB", 4),
    ("AFYA SSA", 3),
    ("UNEB", 2),
    ("UESB CONQUISTA", 1),
]

# Observação: o modelo atual calcula points a partir da posição (POINTS_MAP)
# mas os dados fornecidos já vêm em pontos customizados (20,13,9,...)
# Precisamos então mapear ordem -> position e adaptar POINTS_MAP? Em vez disso,
# salvaremos 'position' conforme ordem e sobrescreveremos points manualmente.

class Command(BaseCommand):
    help = "Popula resultados iniciais de Poker e Xadrez conforme pontuação fornecida. Idempotente."

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Força atualização dos pontos mesmo se já existir resultado.')

    def handle(self, *args, **options):
        force = options['force']
        try:
            poker = Modality.objects.get(name__iexact='POKER')
            xadrez = Modality.objects.get(name__iexact='XADREZ')
        except Modality.DoesNotExist as e:
            raise CommandError('Modalidades POKER e XADREZ precisam existir. Rode seed_modalities primeiro.') from e

        created = 0
        updated = 0
        with transaction.atomic():
            created, updated = self._process_modality(poker, POKER_RESULTS, force, created, updated)
            created, updated = self._process_modality(xadrez, XADREZ_RESULTS, force, created, updated)

        self.stdout.write(self.style.SUCCESS(f"Resultados processados. Criados={created} Atualizados={updated}"))

    def _process_modality(self, modality, rows, force, created, updated):
        # rows é lista de (faculty_name, pontos)
        for idx, (faculty_name, points) in enumerate(rows, start=1):
            faculty = Faculty.objects.filter(name=faculty_name).first()
            if not faculty:
                self.stdout.write(self.style.WARNING(f"Faculdade '{faculty_name}' não encontrada. Pulando."))
                continue
            obj, was_created = Result.objects.get_or_create(modality=modality, position=idx, defaults={'faculty': faculty})
            if was_created:
                # Ajusta pontos customizados
                obj.points = points
                obj.faculty = faculty
                obj.save(update_fields=['points', 'faculty'])
                created += 1
            else:
                changed = False
                if obj.faculty_id != faculty.id:
                    obj.faculty = faculty
                    changed = True
                if force and obj.points != points:
                    obj.points = points
                    changed = True
                if changed:
                    # desabilitar lógica de save que recalcula points: atualiza direto
                    Result.objects.filter(pk=obj.pk).update(faculty=faculty, points=points if force else obj.points)
                    updated += 1
        return created, updated
