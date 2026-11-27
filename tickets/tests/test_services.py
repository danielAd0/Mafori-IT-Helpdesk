"""Milestone 5: the workflow rules in tickets/services.py."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from tickets.models import Category, Ticket
from tickets.services import (
    WorkflowError,
    add_comment,
    assign_ticket,
    change_priority,
    change_status,
    reopen_ticket,
)

Status = Ticket.Status


def make_user(email, role="EMPLOYEE"):
    return get_user_model().objects.create_user(email=email, password="Tr1cky-Horse-Battery!", role=role)


class ServiceTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = make_user("alice@maforigroup.co.za")
        cls.bob = make_user("bob@maforigroup.co.za")
        cls.agent = make_user("agent@maforigroup.co.za", "AGENT")
        cls.other_agent = make_user("agent2@maforigroup.co.za", "AGENT")
        cls.admin = make_user("admin2@maforigroup.co.za", "ADMIN")
        cls.category = Category.objects.create(name="Laptop")

    def setUp(self):
        self.ticket = Ticket.objects.create(
            subject="Laptop slow",
            description="It crawls.",
            category=self.category,
            requester=self.alice,
        )

    def history(self):
        return list(self.ticket.history.values_list("field", "old_value", "new_value"))

    def to_resolved(self):
        assign_ticket(self.ticket, self.agent, self.agent)
        change_status(self.ticket, self.agent, Status.IN_PROGRESS)
        return change_status(self.ticket, self.agent, Status.RESOLVED, "Replaced the battery")

    def to_closed(self):
        self.to_resolved()
        return change_status(self.ticket, self.agent, Status.CLOSED)


class AssignTests(ServiceTestCase):
    def test_assigning_an_open_ticket_makes_it_assigned(self):
        assign_ticket(self.ticket, self.agent, self.agent)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Status.ASSIGNED)
        self.assertEqual(self.ticket.assigned_to, self.agent)
        self.assertCountEqual(
            self.history(),
            [("ASSIGNED_TO", "", self.agent.email), ("STATUS", "OPEN", "ASSIGNED")],
        )

    def test_reassigning_keeps_the_status(self):
        assign_ticket(self.ticket, self.agent, self.agent)
        change_status(self.ticket, self.agent, Status.IN_PROGRESS)
        assign_ticket(self.ticket, self.admin, self.other_agent)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Status.IN_PROGRESS)
        self.assertEqual(self.ticket.assigned_to, self.other_agent)
        self.assertEqual(self.history()[-1], ("ASSIGNED_TO", self.agent.email, self.other_agent.email))

    def test_assigning_to_the_same_agent_writes_nothing(self):
        assign_ticket(self.ticket, self.agent, self.agent)
        assign_ticket(self.ticket, self.agent, self.agent)
        self.assertEqual(len(self.history()), 2)

    def test_an_employee_cannot_assign(self):
        with self.assertRaises(PermissionDenied):
            assign_ticket(self.ticket, self.alice, self.agent)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Status.OPEN)
        self.assertEqual(self.history(), [])

    def test_a_ticket_can_only_go_to_it_staff(self):
        with self.assertRaises(WorkflowError):
            assign_ticket(self.ticket, self.agent, self.bob)

    def test_a_closed_ticket_cannot_be_assigned(self):
        self.to_closed()
        with self.assertRaises(WorkflowError):
            assign_ticket(self.ticket, self.agent, self.other_agent)


class StatusTests(ServiceTestCase):
    def test_the_full_path_to_closed(self):
        self.to_closed()
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Status.CLOSED)
        self.assertEqual(self.ticket.resolution_note, "Replaced the battery")
        self.assertIsNotNone(self.ticket.resolved_at)
        self.assertIsNotNone(self.ticket.closed_at)
        statuses = [row for row in self.history() if row[0] == "STATUS"]
        self.assertEqual(
            statuses,
            [
                ("STATUS", "OPEN", "ASSIGNED"),
                ("STATUS", "ASSIGNED", "IN_PROGRESS"),
                ("STATUS", "IN_PROGRESS", "RESOLVED"),
                ("STATUS", "RESOLVED", "CLOSED"),
            ],
        )

    def test_a_ticket_can_go_on_hold_and_back(self):
        assign_ticket(self.ticket, self.agent, self.agent)
        change_status(self.ticket, self.agent, Status.IN_PROGRESS)
        change_status(self.ticket, self.agent, Status.ON_HOLD)
        change_status(self.ticket, self.agent, Status.IN_PROGRESS)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Status.IN_PROGRESS)

    def test_steps_cannot_be_skipped(self):
        with self.assertRaises(WorkflowError):
            change_status(self.ticket, self.agent, Status.IN_PROGRESS)  # still OPEN
        assign_ticket(self.ticket, self.agent, self.agent)
        with self.assertRaises(WorkflowError):
            change_status(self.ticket, self.agent, Status.RESOLVED, "Done")  # not started

    def test_resolving_needs_a_note(self):
        assign_ticket(self.ticket, self.agent, self.agent)
        change_status(self.ticket, self.agent, Status.IN_PROGRESS)
        with self.assertRaises(WorkflowError):
            change_status(self.ticket, self.agent, Status.RESOLVED, "   ")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Status.IN_PROGRESS)
        self.assertIsNone(self.ticket.resolved_at)

    def test_a_failed_change_writes_no_history(self):
        assign_ticket(self.ticket, self.agent, self.agent)
        before = len(self.history())
        with self.assertRaises(WorkflowError):
            change_status(self.ticket, self.agent, Status.CLOSED)
        self.assertEqual(len(self.history()), before)

    def test_an_employee_cannot_change_status_even_on_their_own_ticket(self):
        assign_ticket(self.ticket, self.agent, self.agent)
        with self.assertRaises(PermissionDenied):
            change_status(self.ticket, self.alice, Status.IN_PROGRESS)

    def test_a_closed_ticket_never_changes(self):
        self.to_closed()
        with self.assertRaises(WorkflowError):
            change_status(self.ticket, self.agent, Status.IN_PROGRESS)

    def test_an_unknown_status_is_refused(self):
        with self.assertRaises(WorkflowError):
            change_status(self.ticket, self.agent, "NOPE")


class ReopenTests(ServiceTestCase):
    def test_the_requester_can_reopen_a_resolved_ticket(self):
        self.to_resolved()
        reopen_ticket(self.ticket, self.alice)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Status.IN_PROGRESS)
        self.assertIsNone(self.ticket.resolved_at)
        self.assertEqual(self.history()[-1], ("STATUS", "RESOLVED", "IN_PROGRESS"))

    def test_nobody_else_can_reopen_it(self):
        self.to_resolved()
        for someone in (self.bob, self.agent, self.admin):
            with self.assertRaises(PermissionDenied):
                reopen_ticket(self.ticket, someone)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Status.RESOLVED)

    def test_only_a_resolved_ticket_can_be_reopened(self):
        with self.assertRaises(WorkflowError):
            reopen_ticket(self.ticket, self.alice)

    def test_a_closed_ticket_cannot_be_reopened(self):
        self.to_closed()
        with self.assertRaises(WorkflowError):
            reopen_ticket(self.ticket, self.alice)


class PriorityTests(ServiceTestCase):
    def test_an_agent_can_change_the_priority(self):
        change_priority(self.ticket, self.agent, "CRITICAL")
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.priority, "CRITICAL")
        self.assertEqual(self.history(), [("PRIORITY", "MEDIUM", "CRITICAL")])

    def test_the_same_priority_writes_nothing(self):
        change_priority(self.ticket, self.agent, "MEDIUM")
        self.assertEqual(self.history(), [])

    def test_an_employee_cannot_change_the_priority(self):
        with self.assertRaises(PermissionDenied):
            change_priority(self.ticket, self.alice, "CRITICAL")

    def test_an_unknown_priority_is_refused(self):
        with self.assertRaises(WorkflowError):
            change_priority(self.ticket, self.agent, "URGENT")

    def test_a_closed_ticket_keeps_its_priority(self):
        self.to_closed()
        with self.assertRaises(WorkflowError):
            change_priority(self.ticket, self.agent, "LOW")


class CommentTests(ServiceTestCase):
    def test_an_employee_can_comment_on_their_own_ticket(self):
        comment = add_comment(self.ticket, self.alice, "Still slow today")
        self.assertFalse(comment.is_internal)
        self.assertEqual(comment.ticket, self.ticket)

    def test_an_employee_cannot_write_an_internal_note(self):
        with self.assertRaises(PermissionDenied):
            add_comment(self.ticket, self.alice, "secret", is_internal=True)

    def test_an_employee_cannot_comment_on_someone_elses_ticket(self):
        with self.assertRaises(PermissionDenied):
            add_comment(self.ticket, self.bob, "Me too")

    def test_an_agent_can_write_an_internal_note(self):
        note = add_comment(self.ticket, self.agent, "Disk is failing", is_internal=True)
        self.assertTrue(note.is_internal)

    def test_an_empty_comment_is_refused(self):
        with self.assertRaises(WorkflowError):
            add_comment(self.ticket, self.alice, "   ")

    def test_a_closed_ticket_takes_no_new_comments(self):
        self.to_closed()
        with self.assertRaises(WorkflowError):
            add_comment(self.ticket, self.alice, "One more thing")
