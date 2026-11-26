"""
Tickets and everything attached to them (owner: Dan).

Rules carried over from the design doc:
  - Users, categories and locations in use can't be deleted (PROTECT); deactivate them instead.
  - TicketHistory rows are written once and never edited or deleted.
  - Status, priority and history field values are checked by the database too,
    not just by the forms.
"""

from django.conf import settings
from django.db import models

from .managers import TicketCommentQuerySet, TicketQuerySet


class Category(models.Model):
    name = models.CharField(max_length=60, unique=True)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Location(models.Model):
    """Where the problem is: an office, floor or site. Managed by admins in the admin panel."""

    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True, help_text="Untick to stop it appearing in the ticket form.")
    sort_order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Lower numbers come first in the dropdown. Equal numbers are sorted by name.",
    )

    class Meta:
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name


class Ticket(models.Model):
    class Priority(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ASSIGNED = "ASSIGNED", "Assigned"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        ON_HOLD = "ON_HOLD", "On hold"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    subject = models.CharField(max_length=150)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="tickets")
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_tickets",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tickets",
    )
    asset_tag = models.CharField(max_length=50, blank=True, help_text="Laptop or printer number, if relevant")
    location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tickets",
        help_text="Office or floor",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    resolution_note = models.TextField(blank=True)

    objects = TicketQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "priority"], name="ticket_queue_idx"),
            models.Index(fields=["assigned_to", "status"], name="ticket_agent_idx"),
            models.Index(fields=["requester", "-created_at"], name="ticket_requester_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=["OPEN", "ASSIGNED", "IN_PROGRESS", "ON_HOLD", "RESOLVED", "CLOSED"]),
                name="ticket_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(priority__in=["LOW", "MEDIUM", "HIGH", "CRITICAL"]),
                name="ticket_priority_valid",
            ),
        ]

    def __str__(self):
        return f"{self.reference} {self.subject}"

    @property
    def reference(self):
        """What people see and quote: MAF-000042."""
        return f"MAF-{self.pk:06d}" if self.pk else ""


class TicketComment(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ticket_comments")
    body = models.TextField()
    is_internal = models.BooleanField(
        default=False,
        help_text="Internal notes are for IT only and are never shown to employees.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = TicketCommentQuerySet.as_manager()

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["ticket", "created_at"], name="comment_ticket_idx")]

    def __str__(self):
        kind = "Internal note" if self.is_internal else "Comment"
        return f"{kind} on {self.ticket.reference} by {self.author}"


class TicketHistory(models.Model):
    """The audit trail: one row per change, written by the app, never edited or deleted."""

    class Field(models.TextChoices):
        STATUS = "STATUS", "Status"
        ASSIGNED_TO = "ASSIGNED_TO", "Assigned to"
        PRIORITY = "PRIORITY", "Priority"
        CATEGORY = "CATEGORY", "Category"

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="history")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ticket_changes")
    field = models.CharField(max_length=12, choices=Field.choices)
    old_value = models.CharField(max_length=100, blank=True)
    new_value = models.CharField(max_length=100, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at", "id"]
        verbose_name_plural = "ticket history"
        indexes = [models.Index(fields=["ticket", "changed_at"], name="history_ticket_idx")]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(field__in=["STATUS", "ASSIGNED_TO", "PRIORITY", "CATEGORY"]),
                name="history_field_valid",
            ),
        ]

    def __str__(self):
        return f"{self.ticket.reference}: {self.field} {self.old_value} -> {self.new_value}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Ticket history can't be edited. Record a new change instead.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Ticket history can't be deleted.")
