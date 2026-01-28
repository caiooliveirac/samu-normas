import json
from django.urls import reverse

def test_version_endpoint(client):
    resp = client.get('/__version__')
    assert resp.status_code == 200
    data = json.loads(resp.content)
    # Campos básicos presentes
    for field in ('sha', 'version', 'build_date'):
        assert field in data
    # Valores default não vazios
    assert data['sha']
