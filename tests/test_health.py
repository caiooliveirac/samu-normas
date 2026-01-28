import pytest


@pytest.mark.django_db
def test_healthz(client):
    from django.test import Client
    c = Client()
    resp = c.get('/healthz')
    assert resp.status_code == 200
    assert resp.content.strip() in (b'ok', b'OK')
