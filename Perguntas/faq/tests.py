from django.test import TestCase, Client


class FAQSmokeTests(TestCase):
	def setUp(self):
		self.client = Client()

	def test_empty_faq_ok(self):
		# Apenas valida que a view principal de FAQ (se houver rota root compartilhada) não quebra.
		resp = self.client.get('/')
		self.assertEqual(resp.status_code, 200)

