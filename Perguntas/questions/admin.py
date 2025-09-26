from django.contrib import admin
from django.utils.html import format_html, format_html_join
from .models import Category, Tag, Rule, RuleCard, RuleBullet, Question

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'status', 'category', 'short_text')
    list_filter = ('status', 'created_at')
    search_fields = ('text', 'ip_hash')

    def short_text(self, obj):
        return (obj.text[:80] + '...') if len(obj.text) > 80 else obj.text
    short_text.short_description = 'Pergunta'

class RuleBulletInline(admin.TabularInline):
    model = RuleBullet
    extra = 1
    autocomplete_fields = ["tags"]
    fields = ("order", "text", "tags")

class RuleCardInline(admin.StackedInline):
    model = RuleCard
    extra = 0
    show_change_link = True

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]

@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ("name", "kind")
    list_filter = ("kind",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}

@admin.register(Rule)
class RuleAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "is_published", "order", "updated_at")
    list_filter = ("is_published", "category")
    search_fields = ("title", "body")
    prepopulated_fields = {"slug": ("title",)}
    inlines = [RuleCardInline]
    ordering = ("order", "title")

    # Exibe um preview somente leitura dos cards/bullets diretamente na página da Regra
    readonly_fields = ("preview",)
    fields = ("title", "slug", "category", "body", "is_published", "order", "preview")

    def preview(self, obj: Rule):
        if not obj or not obj.pk:
            return "Salve a regra para visualizar seus cards e bullets."

        # Monta HTML com os cards e bullets, semelhante ao que a UI React exibe
        parts = []
        for card in obj.cards.all().order_by("order", "id"):
            # Título do card (se não redundante)
            if card.title and card.title.strip().lower() != (obj.title or "").strip().lower():
                parts.append(format_html('<div style="margin-top:8px"><strong>{}</strong></div>', card.title))

            # Lista de bullets
            bullets_html = format_html_join(
                '',
                '<li style="margin:4px 0">{}</li>',
                ((b.text,),) if False else ((b.text,) for b in card.bullets.all().order_by("order", "id"))
            )
            parts.append(format_html('<ul style="margin:6px 0 10px; padding-left:16px">{}</ul>', bullets_html))

        if not parts:
            return "Nenhum card/bullet cadastrado ainda."

        return format_html('<div style="background:#0f152a;border:1px solid rgba(255,255,255,0.08);padding:10px;border-radius:8px">{}</div>',
                           format_html(''.join(str(p) for p in parts)))
    preview.short_description = "Pré-visualização"

@admin.register(RuleCard)
class RuleCardAdmin(admin.ModelAdmin):
    list_display = ("title", "rule", "is_published", "order")
    list_filter = ("is_published", "rule__category")
    search_fields = ("title", "rule__title")
    inlines = [RuleBulletInline]
    ordering = ("rule", "order")

@admin.register(RuleBullet)
class RuleBulletAdmin(admin.ModelAdmin):
    list_display = ("short_text", "card", "order")
    search_fields = ("text", "card__title", "card__rule__title")
    autocomplete_fields = ["card", "tags"]
    ordering = ("card", "order")

    def short_text(self, obj):
        return (obj.text[:80] + "…") if len(obj.text) > 80 else obj.text
