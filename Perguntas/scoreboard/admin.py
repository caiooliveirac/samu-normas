from django.contrib import admin
from .models import Faculty, Modality, Result


@admin.register(Faculty)
class FacultyAdmin(admin.ModelAdmin):
    list_display = ('short_name', 'name', 'total_points')
    search_fields = ('name', 'short_name')


@admin.register(Modality)
class ModalityAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name', 'category')


@admin.register(Result)
class ResultAdmin(admin.ModelAdmin):
    list_display = ('modality', 'position', 'faculty', 'points', 'updated_at')
    list_filter = ('modality', 'faculty')
    search_fields = ('modality__name', 'faculty__name', 'faculty__short_name')
    ordering = ('modality', 'position')
