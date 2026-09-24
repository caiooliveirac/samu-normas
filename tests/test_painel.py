import base64
import hashlib
import hmac
import json
import time

import pytest
from django.contrib.auth.models import User

from questions.federacao import ler_token_handoff
from questions.models import CardRevision, RuleBullet, RuleCard

SEGREDO = "segredo-de-teste-com-tamanho-suficiente"


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def token(segredo=SEGREDO, **claims):
    base = {"tipo": "escala-handoff", "origem": "samu-salvador", "sub": "coord@samu.test",
            "aud": "samu-normas", "iat": int(time.time()), "exp": int(time.time()) + 60,
            "perfil": "COORD_CATEGORIA", "nome": "Coord Teste"}
    base.update(claims)
    cab = _b64(json.dumps({"alg": "HS256"}).encode())
    corpo = _b64(json.dumps(base).encode())
    sig = hmac.new(segredo.encode(), f"{cab}.{corpo}".encode(), hashlib.sha256).digest()
    return f"{cab}.{corpo}.{_b64(sig)}"


@pytest.fixture
def federacao(settings):
    settings.ESCALA_URL = "https://escala.test"
    settings.ESCALA_FEDERACAO_SECRET = SEGREDO
    settings.FEDERACAO_ID = "samu-normas"
    return settings


def test_token_valido():
    assert ler_token_handoff(token(), SEGREDO, "samu-normas")["sub"] == "coord@samu.test"


@pytest.mark.parametrize("tok", [
    token(segredo="outro-segredo"),
    token(aud="huddle"),
    token(exp=int(time.time()) - 1),
    token(tipo="sessao"),
    "lixo",
    "",
])
def test_token_recusado(tok):
    assert ler_token_handoff(tok, SEGREDO, "samu-normas") is None


@pytest.mark.django_db
def test_sso_desligado_sem_env(client, settings):
    settings.ESCALA_FEDERACAO_SECRET = ""
    assert client.get("/api/auth/sso", {"token": token()}).status_code == 404


@pytest.mark.django_db
def test_sso_coordenador_entra_e_ve_painel(client, federacao):
    r = client.get("/api/auth/sso", {"token": token()})
    assert r.status_code == 302 and r["Location"] == "/painel/"
    u = User.objects.get(email="coord@samu.test")
    assert u.is_staff and not u.has_usable_password() and u.first_name == "Coord Teste"
    assert client.get("/painel/").status_code == 200
    assert client.get("/api/me/").json()["coordenacao"] is True


@pytest.mark.django_db
def test_sso_reusa_conta_existente_por_email(client, federacao):
    User.objects.create_user("antigo", email="Coord@Samu.test", password="x")
    client.get("/api/auth/sso", {"token": token()})
    assert User.objects.count() == 1
    assert User.objects.get().is_staff


@pytest.mark.django_db
@pytest.mark.parametrize("perfil", ["ADMIN", "COORD_CATEGORIA"])
def test_sso_admin_e_coordenador_entram(client, federacao, perfil):
    assert client.get("/api/auth/sso", {"token": token(perfil=perfil)}).status_code == 302
    assert client.get("/painel/").status_code == 200
    assert 0 < client.session.get_expiry_age() <= 12 * 3600


@pytest.mark.django_db
@pytest.mark.parametrize("claims", [
    {"perfil": "PROFISSIONAL"},
    {"perfil": "COORD_SETORIAL"},
    {"perfil": ""},
    {"origem": "upas", "perfil": "ADMIN"},
    {"origem": "plantoes", "perfil": "ADMIN"},
])
def test_sso_medico_e_outras_origens_recusados(client, federacao, claims):
    r = client.get("/api/auth/sso", {"token": token(**claims)})
    assert r.status_code == 403
    assert not User.objects.exists()
    assert client.get("/painel/").status_code == 302
    assert client.get("/api/me/").json()["coordenacao"] is False


@pytest.mark.django_db
def test_coordenador_rebaixado_perde_acesso(client, federacao):
    client.get("/api/auth/sso", {"token": token()})
    client.post("/logout/")
    assert client.get("/api/auth/sso", {"token": token(perfil="PROFISSIONAL")}).status_code == 403
    assert not User.objects.get().is_staff


@pytest.mark.django_db
def test_rebaixamento_nao_mexe_em_conta_local(client, federacao):
    User.objects.create_user("admin-local", email="coord@samu.test", password="x", is_staff=True)
    client.get("/api/auth/sso", {"token": token(perfil="PROFISSIONAL")})
    assert User.objects.get().is_staff


@pytest.mark.django_db
def test_entrar_redireciona_ao_handoff_do_escala(client, federacao):
    r = client.get("/painel/entrar/")
    assert r["Location"] == "https://escala.test/api/auth/handoff?para=samu-normas"


@pytest.mark.django_db
def test_anonimo_nao_ve_painel(client):
    assert client.get("/painel/").status_code == 302
    assert client.get("/api/me/").json()["coordenacao"] is False


@pytest.fixture
def coord(client, federacao):
    client.get("/api/auth/sso", {"token": token()})
    return client


def _form(client, card):
    return {"versao": client.get(f"/painel/cards/{card.id}/").context["versao"]}


@pytest.mark.django_db
def test_edicao_de_card_gera_audit_log(coord, published_rule):
    card = RuleCard.objects.get(rule=published_rule)
    b = card.bullets.get()
    dados = _form(coord, card) | {"title": "Card novo", "is_published": "on",
                                  f"bullet-{b.id}": "Bullet editado", "novo": "Item extra"}
    assert coord.post(f"/painel/cards/{card.id}/", dados).status_code == 302

    card.refresh_from_db()
    assert card.title == "Card novo"
    assert list(card.bullets.values_list("text", flat=True)) == ["Bullet editado", "Item extra"]
    rev = CardRevision.objects.get()
    assert rev.user.email == "coord@samu.test" and "coord@samu.test" in rev.user_label
    assert rev.before["title"] == "Card 1" and rev.after["title"] == "Card novo"
    assert coord.get("/painel/historico/").status_code == 200


@pytest.mark.django_db
def test_remover_item_e_sem_mudanca_nao_loga(coord, published_rule):
    card = RuleCard.objects.get(rule=published_rule)
    b = card.bullets.get()
    base = {"title": "Card 1", "is_published": "on", f"bullet-{b.id}": "Bullet 1"}
    coord.post(f"/painel/cards/{card.id}/", _form(coord, card) | base)
    assert not CardRevision.objects.exists()

    coord.post(f"/painel/cards/{card.id}/", _form(coord, card) | base | {f"remover-{b.id}": "on"})
    assert not RuleBullet.objects.filter(pk=b.id).exists()
    assert CardRevision.objects.count() == 1


@pytest.mark.django_db
def test_versao_velha_nao_sobrescreve(coord, published_rule):
    card = RuleCard.objects.get(rule=published_rule)
    velho = _form(coord, card)
    card.title = "Mudado por outro"
    card.save()
    coord.post(f"/painel/cards/{card.id}/", velho | {"title": "Meu título"})
    card.refresh_from_db()
    assert card.title == "Mudado por outro"
    assert not CardRevision.objects.exists()
