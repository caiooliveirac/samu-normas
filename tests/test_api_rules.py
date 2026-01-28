import pytest

@pytest.mark.django_db
def test_api_rules_structure(client, published_rule):
    resp = client.get('/api/rules')
    assert resp.status_code == 200
    data = resp.json()
    assert 'results' in data
    assert len(data['results']) >= 1
    first = data['results'][0]
    assert 'cards' in first and isinstance(first['cards'], list)
    if first['cards']:
        card = first['cards'][0]
        assert 'bullets' in card
