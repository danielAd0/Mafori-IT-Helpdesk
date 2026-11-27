"""
Ticket workflow rules (owner: Jack).

Every change to a ticket goes through one of these functions, never straight
through ticket.save() in a view. Each function:
  - checks who is allowed to do it (PermissionDenied if not),
  - checks the workflow allows it (WorkflowError if not; the message is safe to show),
  - writes the change and its TicketHistory rows in one transaction, so a failed
    change leaves nothing behind.

Workflow:
    OPEN -> ASSIGNED -> IN_PROGRESS -> RESOLVED -> CLOSED
    IN_PROGRESS <-> ON_HOLD
    A RESOLVED ticket can be reopened (back to IN_PROGRESS) by its requester only.
    A CLOSED ticket never changes again.
"""

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from .models import Ticket, TicketComment, TicketHistory

Status = Ticket.Status
Priority = Ticket.Priority
Field = TicketHistory.Field

# Status changes an agent can make with change_status().
# (OPEN -> ASSIGNED happens through assign_ticket(); RESOLVED -> IN_PROGRESS through reopen_ticket().)
NEXT_STATUS = {
    Status.ASSIGNED: {Status.IN_PROGRESS},
    Status.IN_PROGRESS: {Status.ON_HOLD, Status.RESOLVED},
    Status.ON_HOLD: {Status.IN_PROGRESS},
    Status.RESOLVED: {Status.CLOSED},
}


class WorkflowError(Exception):
    """The workflow doesn't allow this change. The message can be shown to the user."""


def _require_it_staff(user):
    if user is None or not user.is_authenticated or not user.is_active or not user.is_it_staff:
        raise PermissionDenied


def _lock(ticket):
    """Reload the ticket and lock its row so two agents can't change it at the same moment."""
    return Ticket.objects.select_for_update().get(pk=ticket.pk)


def _require_not_closed(ticket):
    if ticket.status == Status.CLOSED:
        raise WorkflowError("This ticket is closed and can't be changed.")


def _record(ticket, actor, field, old, new):
    TicketHistory.objects.create(
        ticket=ticket,
        changed_by=actor,
        field=field,
        old_value=old or "",
        new_value=new or "",
    )


@transaction.atomic
def assign_ticket(ticket, actor, agent):
    """Give a ticket to an agent. An OPEN ticket becomes ASSIGNED; reassigning keeps the status."""
    _require_it_staff(actor)
    if agent is None or not agent.is_active or not agent.is_it_staff:
        raise WorkflowError("Tickets can only be assigned to active IT staff.")
    ticket = _lock(ticket)
    _require_not_closed(ticket)
    if ticket.assigned_to_id == agent.pk:
        return ticket

    old_agent = ticket.assigned_to.email if ticket.assigned_to_id else ""
    ticket.assigned_to = agent
    fields = ["assigned_to", "updated_at"]
    _record(ticket, actor, Field.ASSIGNED_TO, old_agent, agent.email)

    if ticket.status == Status.OPEN:
        ticket.status = Status.ASSIGNED
        fields.append("status")
        _record(ticket, actor, Field.STATUS, Status.OPEN, Status.ASSIGNED)

    ticket.save(update_fields=fields)
    return ticket


@transaction.atomic
def change_status(ticket, actor, new_status, resolution_note=""):
    """Move a ticket one step along the workflow. Resolving needs a resolution note."""
    _require_it_staff(actor)
    if new_status not in Status.values:
        raise WorkflowError("Unknown status.")
    ticket = _lock(ticket)
    _require_not_closed(ticket)
    if new_status not in NEXT_STATUS.get(ticket.status, set()):
        current = Status(ticket.status).label.lower()
        wanted = Status(new_status).label.lower()
        raise WorkflowError(f"A ticket that is {current} can't move to {wanted}.")

    fields = ["status", "updated_at"]
    if new_status == Status.RESOLVED:
        note = (resolution_note or "").strip()
        if not note:
            raise WorkflowError("Add a resolution note before resolving a ticket.")
        ticket.resolution_note = note
        ticket.resolved_at = timezone.now()
        fields += ["resolution_note", "resolved_at"]
    elif new_status == Status.CLOSED:
        ticket.closed_at = timezone.now()
        fields.append("closed_at")

    old_status = ticket.status
    ticket.status = new_status
    ticket.save(update_fields=fields)
    _record(ticket, actor, Field.STATUS, old_status, new_status)
    return ticket


@transaction.atomic
def reopen_ticket(ticket, actor):
    """The person who logged a RESOLVED ticket can send it back to IN_PROGRESS."""
    if actor is None or not actor.is_authenticated or not actor.is_active:
        raise PermissionDenied
    ticket = _lock(ticket)
    if ticket.requester_id != actor.pk:
        raise PermissionDenied
    if ticket.status != Status.RESOLVED:
        raise WorkflowError("Only a resolved ticket can be reopened.")

    ticket.status = Status.IN_PROGRESS
    ticket.resolved_at = None
    ticket.save(update_fields=["status", "resolved_at", "updated_at"])
    _record(ticket, actor, Field.STATUS, Status.RESOLVED, Status.IN_PROGRESS)
    return ticket


@transaction.atomic
def change_priority(ticket, actor, priority):
    _require_it_staff(actor)
    if priority not in Priority.values:
        raise WorkflowError("Unknown priority.")
    ticket = _lock(ticket)
    _require_not_closed(ticket)
    if ticket.priority == priority:
        return ticket

    old_priority = ticket.priority
    ticket.priority = priority
    ticket.save(update_fields=["priority", "updated_at"])
    _record(ticket, actor, Field.PRIORITY, old_priority, priority)
    return ticket


@transaction.atomic
def add_comment(ticket, author, body, is_internal=False):
    """Add a comment. Only IT staff can write internal notes; you can only comment on tickets you can see."""
    if not Ticket.objects.visible_to(author).filter(pk=ticket.pk).exists():
        raise PermissionDenied
    if is_internal and not author.is_it_staff:
        raise PermissionDenied
    body = (body or "").strip()
    if not body:
        raise WorkflowError("Write a comment first.")
    ticket = _lock(ticket)
    _require_not_closed(ticket)
    return TicketComment.objects.create(ticket=ticket, author=author, body=body, is_internal=is_internal)
