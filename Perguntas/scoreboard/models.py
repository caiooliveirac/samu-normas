from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

POINTS_MAP = {
    # Escala oficial (top 8): 20, 13, 9, 6, 4, 3, 2, 1
    1: 20,
    2: 13,
    3: 9,
    4: 6,
    5: 4,
    6: 3,
    7: 2,
    8: 1,
}


class Faculty(models.Model):
    name = models.CharField('Faculdade', max_length=120, unique=True)
    short_name = models.CharField('Sigla', max_length=20, unique=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.short_name or self.name

    @property
    def total_points(self):
        return sum(r.points for r in self.results.all())


class Modality(models.Model):
    name = models.CharField('Modalidade', max_length=120, unique=True)
    category = models.CharField('Categoria', max_length=50, blank=True)  # ex: Masculino, Feminino, Misto

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name}{' - ' + self.category if self.category else ''}"


class Result(models.Model):
    faculty = models.ForeignKey(Faculty, related_name='results', on_delete=models.CASCADE)
    modality = models.ForeignKey(Modality, related_name='results', on_delete=models.CASCADE)
    position = models.PositiveSmallIntegerField('Colocação', validators=[MinValueValidator(1), MaxValueValidator(8)])
    points = models.PositiveSmallIntegerField(editable=False, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('modality', 'position')  # cada colocação única por modalidade
        ordering = ['modality', 'position']

    def __str__(self):
        return f"{self.modality} - {self.faculty} ({self.position}º)"

    def save(self, *args, **kwargs):
        """Salva resultado.

        Regras:
        - Por padrão calcula pontos a partir de POINTS_MAP pela posição.
        - Se "points" já estiver > 0 (ex: seed custom) não sobrescreve.
        - Pode forçar recálculo passando kwarg force_points=True.
        """
        force_points = kwargs.pop('force_points', False)
        if force_points or not self.points:
            self.points = POINTS_MAP.get(self.position, 0)
        super().save(*args, **kwargs)
