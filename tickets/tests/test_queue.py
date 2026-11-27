"""Milestone 5: the IT queue page."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Category, Ticket


def make_user(email, role="EMPLOYEE"):
    return get_user_model().objects.create_user(email=email, password="Tr1cky-Horse-Battery!", role=role)


class QueueTestCase(TestCase):
    @classmethod
    def make_ticket(cls, subject, **extra):
        return Ticket.objects.create(
            subject=subject,
            description="Details.",
            category=cls.category,
            requester=cls.alice,
            **extra,
        )

    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user("alice@maforigroup.co.za")
        cls.agent = make_user("agent@maforigroup.co.za", "AGENT")
        cls.admin = make_user("admin2@maforigroup.co.za", "ADMIN")
        cls.category = Category.objects.create(name="Laptop")
        cls.url = reverse("tickets:queue")
        cls.make_ticket("Alice low", priority="LOW")
        cls.make_ticket("Alice critical", priority="CRITICAL")
        cls.make_ticket("Alice high", priority="HIGH")
        cls.make_ticket("Agent job", status="ASSIGNED", assigned_to=cls.agent)
        cls.make_ticket("Old closed job", status="CLOSED")


class QueueAccessTests(QueueTestCase):
    def test_anonymous_is_sent_to_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith(reverse("accounts:login")))

    def test_an_employee_gets_a_403(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_an_employee_gets_a_403_even_on_a_post(self):
        self.client.force_login(self.alice)
        self.assertEqual(self.client.post(self.url).status_code, 403)

    def test_an_agent_can_open_it(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_an_admin_can_open_it(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_the_queue_is_read_only(self):
        self.client.force_login(self.agent)
        self.assertEqual(self.client.post(self.url).status_code, 405)

    def test_the_nav_link_shows_for_it_staff_only(self):
        self.client.force_login(self.agent)
        self.assertContains(self.client.get(reverse("tickets:my_tickets")), self.url)
        self.client.force_login(self.alice)
        self.assertNotContains(self.client.get(reverse("tickets:my_tickets")), self.url)


class QueueContentTests(QueueTestCase):
    def setUp(self):
        self.client.force_login(self.agent)

    def subjects(self, response):
        return [ticket.subject for ticket in response.context["tickets"]]

    def test_it_shows_everyones_active_tickets_and_hides_closed_ones(self):
        response = self.client.get(self.url)
        self.assertContains(response, "Alice low")
        self.assertContains(response, "Agent job")
        self.assertNotContains(response, "Old closed job")

    def test_the_most_urgent_ticket_comes_first(self):
        response = self.client.get(self.url)
        self.assertEqual(self.subjects(response), ["Alice critical", "Alice high", "Agent job", "Alice low"])

    def test_the_closed_tab_shows_closed_tickets_only(self):
        response = self.client.get(self.url, {"status": "CLOSED"})
        self.assertEqual(self.subjects(response), ["Old closed job"])

    def test_filter_by_priority(self):
        response = self.client.get(self.url, {"priority": "HIGH"})
        self.assertEqual(self.subjects(response), ["Alice high"])

    def test_show_only_my_tickets(self):
        response = self.client.get(self.url, {"show": "mine"})
        self.assertEqual(self.subjects(response), ["Agent job"])

    def test_show_only_unassigned_tickets(self):
        response = self.client.get(self.url, {"show": "unassigned"})
        self.assertNotIn("Agent job", self.subjects(response))
        self.assertIn("Alice low", self.subjects(response))

    def test_tampered_filters_are_ignored(self):
        response = self.client.get(self.url, {"status": "HACK", "priority": "NOPE", "show": "everything"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice low")

    def test_status_tabs_show_a_count_for_every_status(self):
        response = self.client.get(self.url)
        counts = {tab["value"]: tab["count"] for tab in response.context["status_tabs"]}
        self.assertEqual(counts["OPEN"], 3)
        self.assertEqual(counts["ASSIGNED"], 1)
        self.assertEqual(counts["CLOSED"], 1)
        self.assertEqual(counts["ON_HOLD"], 0)
