from django.test import TestCase, Client
from django.urls import reverse


class SmokeTests(TestCase):
	def setUp(self):
		self.client = Client()

	def test_home_status_ok(self):
		resp = self.client.get('/')
		self.assertEqual(resp.status_code, 200, 'Home não retornou 200')

	def test_admin_redirect_to_login(self):
		resp = self.client.get('/admin/', follow=False)
		# Admin anônimo deve redirecionar (302)
		self.assertIn(resp.status_code, (301, 302), 'Admin não redirecionou para login')

