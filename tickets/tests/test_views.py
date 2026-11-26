"""Milestone 4: logging tickets and following them."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Category, Ticket, TicketComment, TicketHistory

PASSWORD = "Tr1cky-Horse-Battery!"


def make_user(email, role="EMPLOYEE"):
    return get_user_model().objects.create_user(
        email=email,
        password=PASSWORD,
        first_name="Test",
        last_name=role.title(),
        role=role,
    )


class TicketPageTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user("alice@maforigroup.co.za")
        cls.bob = make_user("bob@maforigroup.co.za")
        cls.agent = make_user("agent@maforigroup.co.za", role="AGENT")
        cls.category = Category.objects.create(name="Laptop")
        cls.retired = Category.objects.create(name="Fax machine", is_active=False)
        cls.alice_ticket = Ticket.objects.create(
            subject="Alice laptop slow",
            description="It crawls.",
            category=cls.category,
            requester=cls.alice,
        )
        cls.bob_ticket = Ticket.objects.create(
            subject="Bob printer jam",
            description="Paper stuck.",
            category=cls.category,
            requester=cls.bob,
        )


class AnonymousTests(TicketPageTestCase):
    def test_every_page_needs_a_login(self):
        urls = [
            reverse("tickets:my_tickets"),
            reverse("tickets:ticket_create"),
            reverse("tickets:ticket_detail", args=[self.alice_ticket.pk]),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertTrue(response["Location"].startswith(reverse("accounts:login")), url)


class MyTicketsTests(TicketPageTestCase):
    def test_lists_only_my_own_tickets(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("tickets:my_tickets"))
        self.assertContains(response, "Alice laptop slow")
        self.assertNotContains(response, "Bob printer jam")

    def test_an_agent_sees_only_the_tickets_they_logged_themselves(self):
        Ticket.objects.create(
            subject="Agent own request",
            description="Mine.",
            category=self.category,
            requester=self.agent,
        )
        self.client.force_login(self.agent)
        response = self.client.get(reverse("tickets:my_tickets"))
        self.assertContains(response, "Agent own request")
        self.assertNotContains(response, "Alice laptop slow")
        self.assertNotContains(response, "Bob printer jam")

    def test_empty_list_says_so(self):
        newcomer = make_user("new@maforigroup.co.za")
        self.client.force_login(newcomer)
        response = self.client.get(reverse("tickets:my_tickets"))
        self.assertContains(response, "haven't logged any tickets")


class LogTicketTests(TicketPageTestCase):
    def data(self, **extra):
        data = {
            "subject": "Cannot print",
            "category": self.category.pk,
            "priority": "HIGH",
            "description": "The printer says offline.",
            "asset_tag": "PRN-12",
            "location": "Floor 2",
        }
        data.update(extra)
        return data

    def test_form_page_loads(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("tickets:ticket_create"))
        self.assertEqual(response.status_code, 200)

    def test_logging_a_ticket(self):
        self.client.force_login(self.alice)
        response = self.client.post(reverse("tickets:ticket_create"), self.data())
        ticket = Ticket.objects.get(subject="Cannot print")
        self.assertRedirects(response, reverse("tickets:ticket_detail", args=[ticket.pk]))
        self.assertEqual(ticket.requester, self.alice)
        self.assertEqual(ticket.status, Ticket.Status.OPEN)
        self.assertEqual(ticket.priority, Ticket.Priority.HIGH)
        self.assertIsNone(ticket.assigned_to)

    def test_requester_status_and_assignee_cannot_be_forged(self):
        self.client.force_login(self.alice)
        forged = self.data(requester=self.bob.pk, status="CLOSED", assigned_to=self.agent.pk)
        self.client.post(reverse("tickets:ticket_create"), forged)
        ticket = Ticket.objects.get(subject="Cannot print")
        self.assertEqual(ticket.requester, self.alice)
        self.assertEqual(ticket.status, Ticket.Status.OPEN)
        self.assertIsNone(ticket.assigned_to)

    def test_subject_is_required(self):
        self.client.force_login(self.alice)
        before = Ticket.objects.count()
        response = self.client.post(reverse("tickets:ticket_create"), self.data(subject=""))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Ticket.objects.count(), before)

    def test_subject_has_a_150_character_limit(self):
        self.client.force_login(self.alice)
        before = Ticket.objects.count()
        response = self.client.post(reverse("tickets:ticket_create"), self.data(subject="x" * 151))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Ticket.objects.count(), before)

    def test_a_retired_category_is_refused(self):
        self.client.force_login(self.alice)
        before = Ticket.objects.count()
        response = self.client.post(reverse("tickets:ticket_create"), self.data(category=self.retired.pk))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Ticket.objects.count(), before)


class TicketDetailTests(TicketPageTestCase):
    def detail_url(self, ticket):
        return reverse("tickets:ticket_detail", args=[ticket.pk])

    def test_owner_sees_their_ticket(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.detail_url(self.alice_ticket))
        self.assertContains(response, "Alice laptop slow")
        self.assertContains(response, self.alice_ticket.reference)

    def test_someone_elses_ticket_is_not_found(self):
        self.client.force_login(self.alice)
        response = self.client.get(self.detail_url(self.bob_ticket))
        self.assertEqual(response.status_code, 404)

    def test_missing_ticket_gives_the_same_not_found(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("tickets:ticket_detail", args=[999999]))
        self.assertEqual(response.status_code, 404)

    def add_comments(self):
        TicketComment.objects.create(
            ticket=self.alice_ticket,
            author=self.agent,
            body="Have you tried restarting?",
            is_internal=False,
        )
        TicketComment.objects.create(
            ticket=self.alice_ticket,
            author=self.agent,
            body="Disk is failing, swap it",
            is_internal=True,
        )

    def test_employee_sees_public_comments_but_never_internal_notes(self):
        self.add_comments()
        self.client.force_login(self.alice)
        response = self.client.get(self.detail_url(self.alice_ticket))
        self.assertContains(response, "Have you tried restarting?")
        self.assertNotContains(response, "Disk is failing")

    def test_agent_sees_internal_notes(self):
        self.add_comments()
        self.client.force_login(self.agent)
        response = self.client.get(self.detail_url(self.alice_ticket))
        self.assertContains(response, "Disk is failing")

    def test_requester_sees_the_history_of_their_ticket(self):
        TicketHistory.objects.create(
            ticket=self.alice_ticket,
            changed_by=self.agent,
            field=TicketHistory.Field.STATUS,
            old_value="OPEN",
            new_value="ASSIGNED",
        )
        self.client.force_login(self.alice)
        response = self.client.get(self.detail_url(self.alice_ticket))
        # The page shows the readable label ("Assigned"), not the stored code ("ASSIGNED")
        self.assertContains(response, "<strong>Open</strong>")
        self.assertContains(response, "<strong>Assigned</strong>")
