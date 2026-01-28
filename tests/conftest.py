import pytest
from django.test import Client
from questions.models import Rule, RuleCard, RuleBullet, Category

@pytest.fixture
def client():
    return Client()

@pytest.fixture
def category(db):
    return Category.objects.create(name="Cat A")

@pytest.fixture
def published_rule(db, category):
    r = Rule.objects.create(title="R1", slug="r1", is_published=True, category=category, order=1)
    card = RuleCard.objects.create(rule=r, title="Card 1", order=1, is_published=True)
    RuleBullet.objects.create(card=card, text="Bullet 1", order=1)
    return r
