"""Tests for the login security rules (one test per rule in the project doc).

Run with:  python manage.py test accounts

make_user() below assumes Dan's User manager has create_user(email, password,
**fields). If his signature differs, change that one helper.
"""

from unittest import mock

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import resolve_url
from django.test import TestCase
from django.urls import reverse

from accounts.lockout import INVALID_MESSAGE, LOCKED_MESSAGE, MAX_FAILED_LOGINS

User = get_user_model()

GOOD_PASSWORD = "Correct-Horse-9!"
NEW_PASSWORD = "Another-Strong-7?x"


def make_user(email="test.employee@example.com", password=GOOD_PASSWORD, **fields):
    fields.setdefault("first_name", "Test")
    fields.setdefault("last_name", "Employee")
    fields.setdefault("role", "EMPLOYEE")
    fields.setdefault("must_change_password", False)
    return User.objects.create_user(email=email, password=password, **fields)


def post_login(client, email, password, **extra):
    return client.post(reverse("accounts:login"), {"email": email, "password": password, **extra})


class LoginTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_correct_login_redirects_into_the_app(self):
        response = post_login(self.client, self.user.email, GOOD_PASSWORD)
        self.assertRedirects(response, resolve_url(settings.LOGIN_REDIRECT_URL), fetch_redirect_response=False)

    def test_email_is_case_insensitive(self):
        response = post_login(self.client, self.user.email.upper(), GOOD_PASSWORD)
        self.assertRedirects(response, resolve_url(settings.LOGIN_REDIRECT_URL), fetch_redirect_response=False)

    def test_wrong_email_and_wrong_password_give_the_same_message(self):
        wrong_password = post_login(self.client, self.user.email, "not-the-password")
        wrong_email = post_login(self.client, "nobody@example.com", "not-the-password")
        self.assertEqual(wrong_password.context["error"], INVALID_MESSAGE)
        self.assertEqual(wrong_email.context["error"], INVALID_MESSAGE)

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save()
        response = post_login(self.client, self.user.email, GOOD_PASSWORD)
        self.assertEqual(response.context["error"], INVALID_MESSAGE)

    def test_login_starts_a_new_session(self):
        self.client.get(reverse("accounts:login"))
        before = self.client.session.session_key
        post_login(self.client, self.user.email, GOOD_PASSWORD)
        self.assertNotEqual(before, self.client.session.session_key)

    def test_login_ignores_a_next_address_on_another_site(self):
        response = post_login(self.client, self.user.email, GOOD_PASSWORD, next="https://evil.example/")
        self.assertRedirects(response, resolve_url(settings.LOGIN_REDIRECT_URL), fetch_redirect_response=False)

    def test_login_follows_a_next_address_on_this_site(self):
        response = post_login(self.client, self.user.email, GOOD_PASSWORD, next="/tickets/")
        self.assertRedirects(response, "/tickets/", fetch_redirect_response=False)


class LockoutTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def fail(self, times):
        for _ in range(times):
            post_login(self.client, self.user.email, "wrong-password")

    def test_five_failures_lock_the_account(self):
        self.fail(MAX_FAILED_LOGINS - 1)
        last = post_login(self.client, self.user.email, "wrong-password")
        self.assertEqual(last.context["error"], LOCKED_MESSAGE)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_logins, MAX_FAILED_LOGINS)

    def test_locked_account_refuses_the_correct_password(self):
        self.fail(MAX_FAILED_LOGINS)
        response = post_login(self.client, self.user.email, GOOD_PASSWORD)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["error"], LOCKED_MESSAGE)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_locked_account_is_not_checked_against_its_password(self):
        self.fail(MAX_FAILED_LOGINS)
        with mock.patch.object(User, "check_password", autospec=True) as check:
            post_login(self.client, self.user.email, GOOD_PASSWORD)
        check.assert_not_called()

    def test_locked_account_stays_at_the_limit(self):
        self.fail(MAX_FAILED_LOGINS + 3)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_logins, MAX_FAILED_LOGINS)

    def test_successful_login_resets_the_counter(self):
        self.fail(3)
        post_login(self.client, self.user.email, GOOD_PASSWORD)
        self.user.refresh_from_db()
        self.assertEqual(self.user.failed_logins, 0)

    def test_an_admin_can_unlock_by_resetting_the_counter(self):
        self.fail(MAX_FAILED_LOGINS)
        self.user.failed_logins = 0
        self.user.save()
        response = post_login(self.client, self.user.email, GOOD_PASSWORD)
        self.assertRedirects(response, resolve_url(settings.LOGIN_REDIRECT_URL), fetch_redirect_response=False)

    def test_lockout_also_applies_to_authenticate_directly(self):
        # The Django admin login uses authenticate(), so it is covered too.
        for _ in range(MAX_FAILED_LOGINS):
            authenticate(username=self.user.email, password="wrong-password")
        self.assertIsNone(authenticate(username=self.user.email, password=GOOD_PASSWORD))


class AccessTests(TestCase):
    def setUp(self):
        self.user = make_user()

    def test_anonymous_visitor_is_sent_to_login(self):
        response = self.client.get(reverse("accounts:change_password"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("accounts:login")))

    def test_logout_must_be_a_post(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)

    def test_logout_ends_the_session(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, resolve_url(settings.LOGOUT_REDIRECT_URL), fetch_redirect_response=False)
        after = self.client.get(reverse("accounts:change_password"))
        self.assertEqual(after.status_code, 302)

    def test_pages_for_logged_in_users_are_not_cached(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("accounts:change_password"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response["Cache-Control"])


class ForcedPasswordChangeTests(TestCase):
    def setUp(self):
        self.user = make_user(must_change_password=True)

    def test_login_goes_to_change_password(self):
        response = post_login(self.client, self.user.email, GOOD_PASSWORD)
        self.assertRedirects(response, reverse("accounts:change_password"), fetch_redirect_response=False)

    def test_every_other_page_redirects_to_change_password(self):
        self.client.force_login(self.user)
        for path in ["/", "/tickets/", "/anything/else/"]:
            response = self.client.get(path)
            self.assertRedirects(response, reverse("accounts:change_password"), fetch_redirect_response=False)

    def test_change_password_page_and_logout_are_still_allowed(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:change_password")).status_code, 200)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, resolve_url(settings.LOGOUT_REDIRECT_URL), fetch_redirect_response=False)

    def change(self, **overrides):
        data = {
            "old_password": GOOD_PASSWORD,
            "new_password1": NEW_PASSWORD,
            "new_password2": NEW_PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse("accounts:change_password"), data)

    def test_new_password_must_differ_from_the_temporary_one(self):
        self.client.force_login(self.user)
        response = self.change(new_password1=GOOD_PASSWORD, new_password2=GOOD_PASSWORD)
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)

    def test_wrong_current_password_is_refused(self):
        self.client.force_login(self.user)
        response = self.change(old_password="not-the-password")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)

    def test_passwords_must_match(self):
        self.client.force_login(self.user)
        response = self.change(new_password2="Something-Else-1!")
        self.assertEqual(response.status_code, 200)

    def test_short_password_is_refused(self):
        self.client.force_login(self.user)
        response = self.change(new_password1="Ab1!xyz", new_password2="Ab1!xyz")
        self.assertEqual(response.status_code, 200)

    def test_common_password_is_refused(self):
        self.client.force_login(self.user)
        response = self.change(new_password1="password123", new_password2="password123")
        self.assertEqual(response.status_code, 200)

    def test_password_similar_to_the_email_is_refused(self):
        self.client.force_login(self.user)
        similar = self.user.email  # the email itself, which is long enough to pass the length rule
        response = self.change(new_password1=similar, new_password2=similar)
        self.assertEqual(response.status_code, 200)

    def test_good_change_clears_the_flag_and_keeps_the_user_logged_in(self):
        self.client.force_login(self.user)
        response = self.change()
        self.assertRedirects(response, resolve_url(settings.LOGIN_REDIRECT_URL), fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password(NEW_PASSWORD))
        # still logged in, and no longer redirected
        self.assertEqual(self.client.get(reverse("accounts:change_password")).status_code, 200)
