from django.core.management.base import BaseCommand
from scoreboard.models import Modality

RAW_MODALITIES = [
    "TENIS DE MESA",
    "POKER",
    "XADREZ",
    "CHEERLEADING",
    "BATERIA",
    "NATACAO",
    "JIU-JITSU",
    "BASQUETE FEM",
    "BASQUETE MASC",
    "VOLEI FEM",
    "VOLEI MASC",
    "HANDEBOL FEM",
    "HANDEBOL MASC",
    "FUTSAL FEM",
    "FUTSAL MASC",
]

class Command(BaseCommand):
    help = "Popula/atualiza lista de modalidades do scoreboard (idempotente)."

    def handle(self, *args, **options):
        created = 0
        for nm in RAW_MODALITIES:
            obj, was_created = Modality.objects.get_or_create(name=nm)
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f"Modalidades processadas. Criadas={created} Total={Modality.objects.count()}"))
