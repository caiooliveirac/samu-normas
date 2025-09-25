from django.contrib import admin
from .models import Question

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at', 'status', 'category', 'short_text')
    list_filter = ('status', 'created_at')
    search_fields = ('text', 'ip_hash')

    def short_text(self, obj):
        return (obj.text[:80] + '...') if len(obj.text) > 80 else obj.text
    short_text.short_description = 'Pergunta'
