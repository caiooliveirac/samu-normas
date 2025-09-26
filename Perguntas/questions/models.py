from django.db import models
from django.utils import timezone
from django.utils.text import slugify

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

class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["name"]

    def __str__(self):
        return self.name

class Tag(models.Model):
    # Opcional: agrupar tags por “domínio” (ex.: segurança, comunicação)
    KIND_CHOICES = [
        ("processo", "Processo"),
        ("seguranca", "Segurança"),
        ("comunicacao", "Comunicação"),
        ("juridico", "Jurídico"),
        ("operacional", "Operacional"),
        ("outros", "Outros"),
    ]
    name = models.CharField(max_length=64, unique=True)
    slug = models.SlugField(max_length=80, unique=True)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default="outros")

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Rule(models.Model):
    """Tópico macro (ex.: Segurança da cena, Biossegurança, Recusa)."""
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    # body agora é opcional/deprecável; cards ocupam seu lugar
    body = models.TextField(blank=True)
    is_published = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    # Busca rápida por texto do próprio Rule (título/corpo)
    class Meta:
        ordering = ["order", "title"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["is_published", "order"]),
        ]

    def __str__(self):
        return (self.title or f"Regra #{self.pk}")


class RuleCard(models.Model):
    """Card exibido na UI; pertence a uma Rule."""
    rule = models.ForeignKey(Rule, on_delete=models.CASCADE, related_name="cards")
    title = models.CharField(max_length=200, help_text="Título do card (opcional).")
    order = models.PositiveIntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Card"
        verbose_name_plural = "Cards"
        ordering = ["rule", "order", "id"]

    def __str__(self):
        return f"{self.rule.title} › {self.title}"


class RuleBullet(models.Model):
    """Cada linha/bullet do card, com tags."""
    card = models.ForeignKey(RuleCard, on_delete=models.CASCADE, related_name="bullets")
    text = models.TextField()
    order = models.PositiveIntegerField(default=0, db_index=True)
    tags = models.ManyToManyField(Tag, blank=True, related_name="bullets")

    class Meta:
        verbose_name = "Bullet"
        verbose_name_plural = "Bullets"
        ordering = ["card", "order", "id"]

    def __str__(self):
        return (self.text[:80] + "…") if len(self.text) > 80 else self.text