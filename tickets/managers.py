"""
Query helpers (owner: Dan).

Every "who can see what" rule lives here, in one place. Views must get their
tickets and comments through these helpers, never with a plain
Ticket.objects.all() or a raw query, so a page can't leak someone else's data.

Examples:
    Ticket.objects.visible_to(request.user)
    Ticket.objects.queue(status="OPEN", priority="HIGH")
    TicketComment.objects.visible_to(request.user).filter(ticket=ticket)
"""

from django.db import models
from django.db.models import Case, Count, IntegerField, Value, When


class TicketQuerySet(models.QuerySet):
    def with_people(self):
        """Fetch category, requester and agent in the same query (avoids one query per row)."""
        return self.select_related("category", "requester", "assigned_to")

    def visible_to(self, user):
        """Tickets this user may see: agents and admins see all, employees only their own."""
        if user is None or not user.is_authenticated or not user.is_active:
            return self.none()
        if user.is_it_staff:
            return self.all()
        return self.filter(requester=user)

    def not_closed(self):
        return self.exclude(status=self.model.Status.CLOSED)

    def queue(self, status=None, priority=None, agent=None, unassigned_only=False):
        """
        The IT queue. Every filter is optional.
          status          one status; leave out to see everything except CLOSED
          priority        one priority
          agent           a User; tickets assigned to them
          unassigned_only only tickets nobody has picked up
        Sorted most urgent first (CRITICAL to LOW), then oldest first.
        Values that aren't real statuses or priorities are ignored, so a
        tampered filter in the URL can't break the page.
        """
        Status, Priority = self.model.Status, self.model.Priority
        qs = self
        if status in Status.values:
            qs = qs.filter(status=status)
        else:
            qs = qs.not_closed()
        if priority in Priority.values:
            qs = qs.filter(priority=priority)
        if unassigned_only:
            qs = qs.filter(assigned_to__isnull=True)
        elif agent is not None:
            qs = qs.filter(assigned_to=agent)
        rank = Case(
            When(priority=Priority.CRITICAL, then=Value(0)),
            When(priority=Priority.HIGH, then=Value(1)),
            When(priority=Priority.MEDIUM, then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
        return qs.annotate(priority_rank=rank).order_by("priority_rank", "created_at", "id")

    def status_counts(self):
        """Every status with its count, zeros included, in workflow order: {"OPEN": 3, ...}."""
        found = dict(self.order_by().values_list("status").annotate(n=Count("id")))
        return {status: found.get(status, 0) for status in self.model.Status.values}

    def active_count_per_agent(self):
        """{agent_id: number of tickets they still have to finish} (not RESOLVED or CLOSED)."""
        Status = self.model.Status
        rows = (
            self.filter(assigned_to__isnull=False)
            .exclude(status__in=[Status.RESOLVED, Status.CLOSED])
            .order_by()
            .values_list("assigned_to")
            .annotate(n=Count("id"))
        )
        return dict(rows)


class TicketCommentQuerySet(models.QuerySet):
    def visible_to(self, user):
        """Comments this user may see: employees never see internal IT notes, or other people's tickets."""
        if user is None or not user.is_authenticated or not user.is_active:
            return self.none()
        if user.is_it_staff:
            return self.all()
        return self.filter(is_internal=False, ticket__requester=user)
