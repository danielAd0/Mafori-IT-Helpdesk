"""Session and CSRF rules from the security section of docs/PROJECT.md."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

PASSWORD = "Tr1cky-Horse-Battery!"


class SessionRulesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email="session.test@maforigroup.co.za",
            password=PASSWORD,
            first_name="Session",
            last_name="Tester",
            role="EMPLOYEE",
        )

    def login(self, client=None):
        client = client or self.client
        return client.post(reverse("accounts:login"), {"email": self.user.email, "password": PASSWORD})

    def test_session_ends_after_30_minutes_of_inactivity(self):
        self.login()
        self.assertEqual(self.client.session.get_expiry_age(), 30 * 60)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)

    def test_session_cookie_is_http_only(self):
        self.login()
        self.assertTrue(self.client.cookies[settings.SESSION_COOKIE_NAME]["httponly"])


class CsrfTests(TestCase):
    def test_login_form_carries_a_csrf_token(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, "csrfmiddlewaretoken")

    def test_login_post_without_a_csrf_token_is_refused(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(reverse("accounts:login"), {"email": "a@b.co.za", "password": "x"})
        self.assertEqual(response.status_code, 403)

    def test_logout_post_without_a_csrf_token_is_refused(self):
        user = get_user_model().objects.create_user(
            email="csrf.test@maforigroup.co.za",
            password=PASSWORD,
            first_name="Csrf",
            last_name="Tester",
            role="EMPLOYEE",
        )
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)
        response = client.post(reverse("accounts:logout"))
        self.assertEqual(response.status_code, 403)
