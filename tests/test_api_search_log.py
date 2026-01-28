import json
import pytest
from django.utils import timezone
from questions.models import SearchLog

@pytest.mark.django_db
def test_search_log_creates_terms(client):
    resp = client.post('/api/search-log', data=json.dumps({
        'term': 'cardiologia avançada teste',
        'results_count': 0
    }), content_type='application/json')
    assert resp.status_code in (200, 201)
    # Deve ter criado termos com tamanho >=4
    terms = list(SearchLog.objects.values_list('term', flat=True))
    assert any('cardio'[:4] in t.lower() or 'cardiologia'[:4] in t.lower() for t in terms)

@pytest.mark.django_db
def test_search_log_ignores_when_results_non_zero(client):
    client.post('/api/search-log', data=json.dumps({'term': 'nao entra', 'results_count': 1}), content_type='application/json')
    assert SearchLog.objects.count() == 0

@pytest.mark.django_db
def test_search_log_dedup_window(client):
    client.post('/api/search-log', data=json.dumps({'term': 'abcde xyzqt', 'results_count': 0}), content_type='application/json')
    first_count = SearchLog.objects.count()
    # Duplica imediatamente
    client.post('/api/search-log', data=json.dumps({'term': 'abcde', 'results_count': 0}), content_type='application/json')
    assert SearchLog.objects.count() == first_count  # sem novo registro immediate
