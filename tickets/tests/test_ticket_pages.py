"""
Milestone 4 page layout (owner: Sifiso).

Jack's test_views.py checks who may see what. These tests check what the
templates show: readable labels, the progress tracker, empty states, the form's
optional fields, and that typed text is escaped.

    python manage.py test tickets.tests.test_ticket_pages
"""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from tickets.models import Category, Ticket, TicketComment, TicketHistory


def make_user(email, role="EMPLOYEE", first_name="Lerato"):
    return get_user_model().objects.create_user(
        email=email,
        password="Tr1cky-Horse-Battery!",
        first_name=first_name,
        last_name="Dlamini",
        role=role,
    )


class TicketPagesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.lerato = make_user("lerato@maforigroup.co.za")
        cls.agent = make_user("thandi@maforigroup.co.za", role="AGENT", first_name="Thandi")
        cls.network = Category.objects.create(name="Network")
        cls.retired = Category.objects.create(name="Fax machine", is_active=False)
        cls.ticket = Ticket.objects.create(
            subject="VPN drops every hour",
            description="Line one.\nLine two.",
            category=cls.network,
            priority=Ticket.Priority.HIGH,
            status=Ticket.Status.IN_PROGRESS,
            requester=cls.lerato,
            assigned_to=cls.agent,
            asset_tag="MAF-LT-0193",
        )

    def setUp(self):
        self.client.force_login(self.lerato)

    def detail(self, ticket=None):
        return self.client.get(reverse("tickets:ticket_detail", args=[(ticket or self.ticket).pk]))


class MyTicketsPageTests(TicketPagesTestCase):
    def test_rows_show_readable_badges_and_link_to_the_ticket(self):
        response = self.client.get(reverse("tickets:my_tickets"))
        self.assertContains(response, "badge--status-in_progress")
        self.assertContains(response, "In progress")
        self.assertContains(response, "badge--priority-high")
        self.assertContains(response, reverse("tickets:ticket_detail", args=[self.ticket.pk]))
        self.assertContains(response, "1 ticket logged by you")

    def test_cells_are_labelled_for_the_phone_layout(self):
        response = self.client.get(reverse("tickets:my_tickets"))
        for label in ("Ticket", "Subject", "Category", "Priority", "Status", "Logged"):
            self.assertContains(response, f'data-label="{label}"')

    def test_empty_list_offers_to_log_a_ticket(self):
        self.client.force_login(self.agent)  # the agent hasn't logged any tickets
        response = self.client.get(reverse("tickets:my_tickets"))
        self.assertContains(response, "Log your first ticket")
        self.assertNotContains(response, "<table")


class LogTicketPageTests(TicketPagesTestCase):
    def test_optional_fields_are_marked(self):
        response = self.client.get(reverse("tickets:ticket_create"))
        self.assertContains(response, "(optional)", count=2)  # asset tag and location

    def test_help_text_has_an_id_for_screen_readers(self):
        response = self.client.get(reverse("tickets:ticket_create"))
        self.assertContains(response, 'id="id_asset_tag_helptext"')

    def test_retired_categories_are_not_offered(self):
        response = self.client.get(reverse("tickets:ticket_create"))
        self.assertContains(response, "Network")
        self.assertNotContains(response, "Fax machine")

    def test_errors_are_summarised_at_the_top(self):
        response = self.client.post(reverse("tickets:ticket_create"), {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "highlighted field")
        self.assertContains(response, "field--invalid")


class TicketDetailPageTests(TicketPagesTestCase):
    def test_progress_tracker_marks_the_current_step(self):
        response = self.detail()
        self.assertContains(response, 'aria-current="step"', count=1)
        self.assertContains(response, "Being worked on")

    def test_on_hold_is_shown_in_the_tracker(self):
        self.ticket.status = Ticket.Status.ON_HOLD
        self.ticket.save()
        self.assertContains(self.detail(), "steps__item--hold")

    def test_history_uses_words_not_codes(self):
        TicketHistory.objects.create(
            ticket=self.ticket,
            changed_by=self.agent,
            field=TicketHistory.Field.STATUS,
            old_value="ASSIGNED",
            new_value="IN_PROGRESS",
        )
        response = self.detail()
        self.assertContains(response, "<strong>In progress</strong>")
        self.assertNotContains(response, "IN_PROGRESS")

    def test_assignment_history_reads_naturally(self):
        TicketHistory.objects.create(
            ticket=self.ticket,
            changed_by=self.agent,
            field=TicketHistory.Field.ASSIGNED_TO,
            old_value="",
            new_value="thandi@maforigroup.co.za",
        )
        self.assertContains(self.detail(), "Assigned to thandi@maforigroup.co.za")

    def test_details_panel(self):
        response = self.detail()
        self.assertContains(response, "Thandi Dlamini")  # assigned agent's full name
        self.assertContains(response, "MAF-LT-0193")
        self.assertNotContains(response, "<dt>Location</dt>")  # left blank, so hidden

    def test_internal_notes_are_labelled_for_agents(self):
        TicketComment.objects.create(ticket=self.ticket, author=self.agent, body="Swap the disk", is_internal=True)
        self.client.force_login(self.agent)
        response = self.detail()
        self.assertContains(response, "comment--internal")
        self.assertContains(response, "Internal note: IT only")

    def test_employee_never_gets_the_internal_label_or_note(self):
        TicketComment.objects.create(ticket=self.ticket, author=self.agent, body="Swap the disk", is_internal=True)
        response = self.detail()
        self.assertNotContains(response, "Swap the disk")
        self.assertNotContains(response, "Internal note")
        self.assertContains(response, "No comments yet")

    def test_typed_text_is_escaped(self):
        sneaky = Ticket.objects.create(
            subject="<script>alert(1)</script>",
            description="<b>bold?</b>",
            category=self.network,
            requester=self.lerato,
        )
        response = self.detail(sneaky)
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<b>bold?</b>")

    def test_resolution_note_is_shown_when_resolved(self):
        self.ticket.status = Ticket.Status.RESOLVED
        self.ticket.resolution_note = "Updated the VPN client."
        self.ticket.save()
        response = self.detail()
        self.assertContains(response, "How IT resolved it")
        self.assertContains(response, "Updated the VPN client.")
