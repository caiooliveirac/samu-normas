from django.core.management.base import BaseCommand
from django.utils import timezone

import datetime

from questions.models import ChecklistDigestLog
from questions.views import _build_checklist_digest_for_date, _send_telegram_message


class Command(BaseCommand):
    help = "Envia digest diário de checklists via Telegram (faltantes + faltas/obs)."

    def add_arguments(self, parser):
        parser.add_argument('--date', default='', help='Data AAAA-MM-DD (default: hoje)')
        parser.add_argument('--slot', default='manual', help='Slot (morning|midday|evening|manual)')
        parser.add_argument('--force', action='store_true', help='Força envio mesmo se já enviado no slot')

    def handle(self, *args, **opts):
        date_raw = (opts.get('date') or '').strip()
        slot = (opts.get('slot') or 'manual').strip()[:32]
        force = bool(opts.get('force'))

        if date_raw:
            try:
                day = datetime.date.fromisoformat(date_raw)
            except ValueError:
                raise SystemExit('Data inválida (use AAAA-MM-DD).')
        else:
            day = timezone.localdate()

        if not force and ChecklistDigestLog.objects.filter(date=day, slot=slot, status='success').exists():
            self.stdout.write(self.style.WARNING('Já enviado (skipped).'))
            return

        digest = _build_checklist_digest_for_date(day)
        msg = digest['message']

        send = _send_telegram_message(msg)
        status = 'success' if send.get('ok') else 'error'
        recipient = ','.join(send.get('sent_to') or [])

        ChecklistDigestLog.objects.update_or_create(
            date=day,
            slot=slot,
            defaults={
                'sent_at': timezone.now(),
                'status': status,
                'recipient': recipient,
                'message': msg,
                'error': (send.get('error') or '')[:4000],
            },
        )

        if not send.get('ok'):
            raise SystemExit(send.get('error') or 'Falha ao enviar no Telegram.')

        self.stdout.write(self.style.SUCCESS(f"Enviado no Telegram para: {recipient or '(desconhecido)'}"))
