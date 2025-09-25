from django.db import models
from django.utils import timezone
import hashlib

def hash_ip(ip: str) -> str:
    if not ip:
        return ''
    return hashlib.sha256(ip.encode('utf-8')).hexdigest()

class Question(models.Model):
    STATUS_NEW = 'new'
    STATUS_REVIEWED = 'reviewed'
    STATUS_CHOICES = [
        (STATUS_NEW, 'Novo'),
        (STATUS_REVIEWED, 'Revisado'),
    ]

    text = models.TextField('Pergunta')
    category = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    ip_hash = models.CharField(max_length=64, blank=True)

    def set_ip(self, ip):
        self.ip_hash = hash_ip(ip)

    def __str__(self):
        text = (self.text or "").strip()
        preview = (text[:50] + "…") if len(text) > 50 else (text or "(vazio)")
        return f"Pergunta #{self.pk or '?'} — {preview}"
