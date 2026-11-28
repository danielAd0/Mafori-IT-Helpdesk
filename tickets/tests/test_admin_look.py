"""
The Mafori look on Django's admin panel (owner: Sifiso).

Checks the template overrides in templates/admin/ render for a real admin:
logo header, links back to the app, and the grouped home-page cards.

    python manage.py test tickets.tests.test_admin_look
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class AdminLookTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_user(
            email="admin.test@maforigroup.co.za",
            password="Tr1cky-Horse-Battery!",
            first_name="Ayanda",
            role="ADMIN",
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def home(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        return response

    def test_header_shows_the_logo_and_admin_tag(self):
        response = self.home()
        self.assertContains(response, 'img/mafori-logo.png" alt="Mafori"')
        self.assertContains(response, "mf-brand__tag")

    def test_links_go_back_to_the_app(self):
        response = self.home()
        self.assertContains(response, "Back to the helpdesk")
        self.assertNotContains(response, "View site")
        self.assertContains(response, f'href="{reverse("accounts:change_password")}"')
        self.assertContains(response, f'action="{reverse("accounts:logout")}"')

    def test_home_page_groups_models_into_cards(self):
        response = self.home()
        for heading in ("People", "Ticket setup", "Records"):
            self.assertContains(response, f">{heading}</h2>")
        for url_name in (
            "admin:accounts_user_changelist",
            "admin:accounts_department_changelist",
            "admin:tickets_category_changelist",
            "admin:tickets_location_changelist",
            "admin:tickets_ticket_changelist",
            "admin:tickets_tickethistory_changelist",
        ):
            self.assertContains(response, f'href="{reverse(url_name)}"')

    def test_groups_are_left_off_the_home_page(self):
        self.assertNotContains(self.home(), reverse("admin:auth_group_changelist"))

    def test_other_pages_still_work(self):
        for url_name in ("admin:accounts_user_changelist", "admin:tickets_location_add"):
            self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_signed_out_login_page_shows_the_logo(self):
        self.client.logout()
        response = self.client.get(reverse("admin:login"))
        self.assertContains(response, 'img/mafori-logo.png" alt="Mafori"')
