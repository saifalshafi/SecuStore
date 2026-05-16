from django.test import TestCase, Client
from django.contrib.auth.models import User

class BasicTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser', password='Test@1234', email='test@test.com'
        )

    def test_login_page(self):
        response = self.client.get('/Accounts/login/')
        self.assertEqual(response.status_code, 200)

    def test_signup_page(self):
        response = self.client.get('/Accounts/signup/')
        self.assertEqual(response.status_code, 200)

    def test_file_management_requires_login(self):
        response = self.client.get('/files/')
        self.assertEqual(response.status_code, 302)

    def test_dashboard_requires_staff(self):
        response = self.client.get('/monitoring/dashboard/')
        self.assertEqual(response.status_code, 302)

    def test_password_reset_page(self):
        response = self.client.get('/Accounts/password_reset/')
        self.assertEqual(response.status_code, 200)