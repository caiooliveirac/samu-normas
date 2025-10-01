import pytest
from questions.models import Question, AskedTerm

@pytest.mark.django_db
def test_ask_view_creates_question_and_terms(client):
    data = { 'text': 'Qual protocolo cardiologia emergencias?', 'category': '' }
    resp = client.post('/ask/', data)
    # Redireciona após sucesso
    assert resp.status_code in (302, 301)
    assert Question.objects.count() == 1
    # AskedTerm deve ter pelo menos um termo com >=4 chars
    assert AskedTerm.objects.count() >= 1

@pytest.mark.django_db
def test_ask_view_invalid_form(client):
    resp = client.post('/ask/', {'text': ''})
    # Recarrega página com erro
    assert resp.status_code == 200
    assert Question.objects.count() == 0
