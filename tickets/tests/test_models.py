from datetime import timedelta

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from tickets.models import Category, Ticket, TicketComment, TicketHistory


class HelpdeskTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hardware = Category.objects.create(name="Hardware")
        cls.staff = User.objects.create_user("staff@maforigroup.co.za", "x")
        cls.other = User.objects.create_user("other@maforigroup.co.za", "x")
        cls.agent = User.objects.create_user("agent@maforigroup.co.za", "x", role=User.Role.AGENT)
        cls.agent2 = User.objects.create_user("agent2@maforigroup.co.za", "x", role=User.Role.AGENT)
        cls.admin = User.objects.create_user("admin@maforigroup.co.za", "x", role=User.Role.ADMIN)

    def ticket(self, requester=None, **kwargs):
        kwargs.setdefault("subject", "Something broke")
        kwargs.setdefault("description", "Details")
        kwargs.setdefault("category", self.hardware)
        return Ticket.objects.create(requester=requester or self.staff, **kwargs)


class TicketModelTests(HelpdeskTestCase):
    def test_reference_format(self):
        t = self.ticket()
        self.assertEqual(t.reference, f"MAF-{t.pk:06d}")
        self.assertRegex(t.reference, r"^MAF-\d{6}$")

    def test_defaults(self):
        t = self.ticket()
        self.assertEqual(t.status, Ticket.Status.OPEN)
        self.assertEqual(t.priority, Ticket.Priority.MEDIUM)
        self.assertIsNone(t.assigned_to)

    def test_database_rejects_unknown_status_and_priority(self):
        t = self.ticket()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ticket.objects.filter(pk=t.pk).update(status="DONE")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ticket.objects.filter(pk=t.pk).update(priority="URGENT")

    def test_requester_with_tickets_cannot_be_deleted(self):
        self.ticket()
        with self.assertRaises(ProtectedError):
            self.staff.delete()

    def test_category_in_use_cannot_be_deleted(self):
        self.ticket()
        with self.assertRaises(ProtectedError):
            self.hardware.delete()


class VisibilityTests(HelpdeskTestCase):
    def test_employee_sees_only_own_tickets(self):
        mine = self.ticket(self.staff)
        self.ticket(self.other)
        self.assertEqual(list(Ticket.objects.visible_to(self.staff)), [mine])

    def test_agents_and_admins_see_all(self):
        self.ticket(self.staff)
        self.ticket(self.other)
        self.assertEqual(Ticket.objects.visible_to(self.agent).count(), 2)
        self.assertEqual(Ticket.objects.visible_to(self.admin).count(), 2)

    def test_inactive_or_missing_user_sees_nothing(self):
        self.ticket(self.staff)
        gone = User.objects.create_user("gone@maforigroup.co.za", "x", role=User.Role.AGENT, is_active=False)
        self.assertEqual(Ticket.objects.visible_to(gone).count(), 0)
        self.assertEqual(Ticket.objects.visible_to(None).count(), 0)

    def test_employee_never_sees_internal_notes(self):
        t = self.ticket(self.staff)
        public = TicketComment.objects.create(ticket=t, author=self.agent, body="On my way")
        TicketComment.objects.create(ticket=t, author=self.agent, body="Warranty check", is_internal=True)
        self.assertEqual(list(TicketComment.objects.visible_to(self.staff)), [public])
        self.assertEqual(TicketComment.objects.visible_to(self.agent).count(), 2)

    def test_employee_cannot_read_comments_on_others_tickets(self):
        theirs = self.ticket(self.other)
        TicketComment.objects.create(ticket=theirs, author=self.agent, body="Public reply")
        self.assertEqual(TicketComment.objects.visible_to(self.staff).count(), 0)


class QueueTests(HelpdeskTestCase):
    def setUp(self):
        now = timezone.now()

        def make(priority, status=Ticket.Status.OPEN, agent=None, days_ago=0):
            t = self.ticket(priority=priority, status=status, assigned_to=agent)
            Ticket.objects.filter(pk=t.pk).update(created_at=now - timedelta(days=days_ago))
            return t

        self.low_old = make(Ticket.Priority.LOW, days_ago=9)
        self.critical = make(Ticket.Priority.CRITICAL, days_ago=1)
        self.high_new = make(Ticket.Priority.HIGH, agent=self.agent, status=Ticket.Status.ASSIGNED, days_ago=1)
        self.high_old = make(Ticket.Priority.HIGH, agent=self.agent2, status=Ticket.Status.IN_PROGRESS, days_ago=5)
        self.closed = make(Ticket.Priority.CRITICAL, status=Ticket.Status.CLOSED, agent=self.agent, days_ago=20)

    def ids(self, qs):
        return [t.pk for t in qs]

    def test_default_queue_hides_closed_and_sorts_by_urgency_then_age(self):
        self.assertEqual(
            self.ids(Ticket.objects.queue()),
            [self.critical.pk, self.high_old.pk, self.high_new.pk, self.low_old.pk],
        )

    def test_filters(self):
        self.assertEqual(self.ids(Ticket.objects.queue(status="CLOSED")), [self.closed.pk])
        self.assertEqual(self.ids(Ticket.objects.queue(priority="HIGH")), [self.high_old.pk, self.high_new.pk])
        self.assertEqual(self.ids(Ticket.objects.queue(agent=self.agent)), [self.high_new.pk])
        self.assertEqual(self.ids(Ticket.objects.queue(unassigned_only=True)), [self.critical.pk, self.low_old.pk])

    def test_tampered_filters_are_ignored(self):
        self.assertEqual(
            self.ids(Ticket.objects.queue(status="x' OR '1'='1", priority="BOGUS")),
            self.ids(Ticket.objects.queue()),
        )

    def test_status_counts_include_zeros_in_workflow_order(self):
        counts = Ticket.objects.status_counts()
        self.assertEqual(list(counts), list(Ticket.Status.values))
        self.assertEqual(counts["OPEN"], 2)
        self.assertEqual(counts["ON_HOLD"], 0)
        self.assertEqual(sum(counts.values()), 5)

    def test_status_counts_for_one_requester(self):
        self.ticket(self.other)
        self.assertEqual(Ticket.objects.visible_to(self.other).status_counts()["OPEN"], 1)

    def test_active_count_per_agent_skips_finished_tickets(self):
        self.assertEqual(Ticket.objects.active_count_per_agent(), {self.agent.pk: 1, self.agent2.pk: 1})


class HistoryTests(HelpdeskTestCase):
    def test_history_cannot_be_edited_or_deleted(self):
        t = self.ticket()
        h = TicketHistory.objects.create(
            ticket=t, changed_by=self.agent, field="STATUS", old_value="OPEN", new_value="ASSIGNED"
        )
        h.new_value = "CLOSED"
        with self.assertRaises(ValueError):
            h.save()
        with self.assertRaises(ValueError):
            h.delete()

    def test_database_rejects_unknown_history_field(self):
        t = self.ticket()
        with self.assertRaises(IntegrityError), transaction.atomic():
            TicketHistory.objects.create(ticket=t, changed_by=self.agent, field="SUBJECT")


class StartingDataTests(TestCase):
    def test_initial_data_loads(self):
        call_command("loaddata", "initial_data", verbosity=0)
        self.assertEqual(Category.objects.filter(is_active=True).count(), 7)
        from accounts.models import Department

        self.assertEqual(Department.objects.count(), 6)

    @override_settings(DEBUG=True)
    def test_seed_demo_runs_twice_without_duplicates(self):
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(User.objects.count(), 3)
        self.assertEqual(Ticket.objects.count(), 3)
        staff = User.objects.get(email="staff@maforigroup.co.za")
        self.assertTrue(staff.check_password("Staff@2026"))

    @override_settings(DEBUG=False)
    def test_seed_demo_refuses_without_debug(self):
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command("seed_demo", verbosity=0)
