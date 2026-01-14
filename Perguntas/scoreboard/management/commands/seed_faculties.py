from django.core.management.base import BaseCommand
from scoreboard.models import Faculty

RAW_FACULTIES = [
    "UNIFG GUANAMBI",
    "AFYA SSA",
    "INDOMED ALAGOINHAS",
    "UNEX FSA",
    "ZARNS",
    "UFRB",
    "ESTÁCIO JUAZEIRO",
    "UESB JEQUIÉ",
    "UESB CONQUISTA",
    "UNIFACS",
    "UNEB",
    "UFBA CAT",
    "UNIME",
    "UEFS",
    "BAHIANA",
    "UFOB",
    "UFBA",
    "UESC",
    "UNINASSAU BARREIRAS",
    "UNIFG BRUMADO",
]


def to_short(name: str) -> str:
    # Regras simples: pega primeira parte ou sigla já curta; limita 12 chars.
    parts = name.split()
    if len(parts) == 1:
        base = parts[0]
    else:
        # Se começa com UF/UN/UE etc e segunda parte curta, junta duas
        base = parts[0]
        if base.endswith(('FG', 'FB', 'FBA')) and len(parts) > 1:
            base = f"{base} {parts[1]}"  # manter padrão legível
    short = name[:12].upper()
    return short

class Command(BaseCommand):
    help = "Popula/atualiza lista de faculdades do scoreboard (idempotente)."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for nm in RAW_FACULTIES:
            short = to_short(nm)
            obj, was_created = Faculty.objects.get_or_create(name=nm, defaults={'short_name': short})
            if was_created:
                created += 1
            else:
                # Atualiza short_name se mudou (evita quebrar unique se conflitar)
                if obj.short_name != short:
                    if not Faculty.objects.exclude(pk=obj.pk).filter(short_name=short).exists():
                        obj.short_name = short
                        obj.save(update_fields=['short_name'])
                        updated += 1
        self.stdout.write(self.style.SUCCESS(f"Faculdades processadas. Criadas={created} Atualizadas={updated} Total={Faculty.objects.count()}"))
