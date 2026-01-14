from django.test import TestCase
from django.urls import reverse
from .models import Faculty, Modality, Result


class ScoreboardTests(TestCase):
    def setUp(self):
        f1 = Faculty.objects.create(name='Faculdade A', short_name='A')
        f2 = Faculty.objects.create(name='Faculdade B', short_name='B')
        m1 = Modality.objects.create(name='Futsal')
        m2 = Modality.objects.create(name='Vôlei')
        Result.objects.create(faculty=f1, modality=m1, position=1)  # 9 pts
        Result.objects.create(faculty=f2, modality=m1, position=2)  # 7 pts
        Result.objects.create(faculty=f2, modality=m2, position=1)  # 9 pts

    def test_scoreboard_data(self):
        url = reverse('scoreboard:data')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()['faculties']
        # Ordenado desc por total
        self.assertEqual(data[0]['short_name'], 'B')  # B: 16 pts
        self.assertEqual(data[0]['total'], 16)
        self.assertEqual(data[1]['short_name'], 'A')  # A: 9 pts
        self.assertEqual(data[1]['total'], 9)
