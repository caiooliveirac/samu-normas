from django.core.management.base import BaseCommand
from scoreboard.models import Result, POINTS_MAP

class Command(BaseCommand):
    help = "Recalcula os pontos de todos os resultados conforme POINTS_MAP atual."

    def add_arguments(self, parser):
        parser.add_argument('--modality', help='Filtrar por modalidade (name exato ou case-insensitive).', default=None)
        parser.add_argument('--dry-run', action='store_true', help='Apenas exibe mudanças, não salva.')

    def handle(self, *args, **options):
        modality_name = options['modality']
        dry = options['dry_run']
        qs = Result.objects.all()
        if modality_name:
            qs = qs.filter(modality__name__iexact=modality_name)
        changed = 0
        total = 0
        for r in qs.select_related('modality', 'faculty').order_by('modality__name', 'position'):
            total += 1
            expected = POINTS_MAP.get(r.position, 0)
            if r.points != expected:
                self.stdout.write(f"{r.modality.name} {r.position}º {r.faculty}: {r.points} -> {expected}")
                if not dry:
                    r.points = expected
                    r.save(update_fields=['points'])
                changed += 1
        self.stdout.write(self.style.SUCCESS(f"Resultados processados: {total}. Alterados: {changed}. Dry-run={dry}"))
