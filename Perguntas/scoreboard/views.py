from django.db.models import Sum, Count, Q
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from .models import Faculty, Result, Modality


def scoreboard_view(request):
    # Renderiza página principal (JS fará polling)
    return render(request, 'scoreboard/scoreboard.html')


def scoreboard_data(request):
    # Agrega pontos por faculdade (quadro geral)
    data = (
        Faculty.objects
        .annotate(
            total=Sum('results__points'),
            gold=Count('results', filter=Q(results__position=1)),
            silver=Count('results', filter=Q(results__position=2)),
            bronze=Count('results', filter=Q(results__position=3)),
        )
        .order_by('-total', 'short_name')
        .values('short_name', 'name', 'total', 'gold', 'silver', 'bronze')
    )
    faculties_payload = [
        {
            'short_name': row['short_name'],
            'name': row['name'],
            'total': row['total'] or 0,
            'gold': row['gold'] or 0,
            'silver': row['silver'] or 0,
            'bronze': row['bronze'] or 0,
        }
        for row in data
    ]

    # Modalidades (todas, mesmo sem resultados) para permitir página com mensagem amigável
    modalities_qs = (
        Modality.objects
        .all()
        .order_by('name', 'category')
    )
    modalities_payload = []
    for m in modalities_qs:
        results = (
            Result.objects
            .filter(modality=m)
            .select_related('faculty')
            .order_by('position')
            .values('position', 'points', 'faculty__short_name', 'faculty__name')
        )
        modalities_payload.append({
            'id': m.id,
            'name': m.name,
            'category': m.category,
            'results': [
                {
                    'position': r['position'],
                    'points': r['points'],
                    'faculty': r['faculty__short_name'] or r['faculty__name'],
                    'faculty_full': r['faculty__name'],
                }
                for r in results
            ]
        })

    # Quadro de medalhas (ouro/prata/bronze por faculdade)
    medals_qs = (
        Faculty.objects
        .annotate(
            gold=Count('results', filter=Q(results__position=1)),
            silver=Count('results', filter=Q(results__position=2)),
            bronze=Count('results', filter=Q(results__position=3)),
        )
        .annotate(total=Sum('results__points'))
        .values('short_name', 'name', 'gold', 'silver', 'bronze', 'total')
    )
    medals = [
        {
            'short_name': row['short_name'],
            'name': row['name'],
            'gold': row['gold'] or 0,
            'silver': row['silver'] or 0,
            'bronze': row['bronze'] or 0,
            'total_points': row['total'] or 0,
            'score': (row['gold'] or 0) * 3 + (row['silver'] or 0) * 2 + (row['bronze'] or 0) * 1,
        }
        for row in medals_qs
    ]
    # Ordenação: mais ouros, depois pratas, depois bronzes; como fallback, total de pontos
    medals.sort(key=lambda x: (-x['gold'], -x['silver'], -x['bronze'], -x['total_points'], x['short_name'] or x['name']))

    return JsonResponse({'faculties': faculties_payload, 'modalities': modalities_payload, 'medals': medals})


def faculty_detail(request, short_name: str):
    faculty = get_object_or_404(Faculty, short_name__iexact=short_name)
    results = (
        Result.objects
        .filter(faculty=faculty)
        .select_related('modality')
        .order_by('modality__name', 'modality__category', 'position')
    )
    context = {
        'faculty': faculty,
        'results': results,
    }
    return render(request, 'scoreboard/faculty_detail.html', context)


def modality_detail(request, pk: int):
    modality = get_object_or_404(Modality, pk=pk)
    results = (
        Result.objects
        .filter(modality=modality)
        .select_related('faculty')
        .order_by('position')
    )
    context = {
        'modality': modality,
        'results': results,
    }
    return render(request, 'scoreboard/modality_detail.html', context)
