"""Ticket pages.

Employee side (Milestone 4): my tickets, log a ticket, ticket detail.
IT side (Milestone 5): the IT queue.

Every ticket and comment lookup goes through Dan's visible_to() helpers, so a
person can never reach someone else's data by changing the URL.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from .forms import TicketForm
from .models import Ticket, TicketComment
from .permissions import it_staff_required


def my_tickets(request):
    """The tickets this person logged, newest first."""
    tickets = Ticket.objects.visible_to(request.user).filter(requester=request.user).with_people()
    return render(request, "tickets/my_tickets.html", {"tickets": tickets})


@require_http_methods(["GET", "POST"])
def ticket_create(request):
    if request.method == "POST":
        form = TicketForm(request.POST)
        if form.is_valid():
            ticket = form.save(commit=False)
            ticket.requester = request.user  # never taken from the form
            ticket.save()
            messages.success(request, f"Ticket {ticket.reference} logged.")
            return redirect("tickets:ticket_detail", pk=ticket.pk)
    else:
        form = TicketForm()
    return render(request, "tickets/ticket_form.html", {"form": form})


def ticket_detail(request, pk):
    """One ticket with its comments and history.

    Someone else's ticket gives the same 404 as a ticket that doesn't exist.
    """
    ticket = get_object_or_404(Ticket.objects.visible_to(request.user).with_people(), pk=pk)
    comments = TicketComment.objects.visible_to(request.user).filter(ticket=ticket).select_related("author")
    history = ticket.history.select_related("changed_by")
    context = {"ticket": ticket, "comments": comments, "history": history}
    return render(request, "tickets/ticket_detail.html", context)


@it_staff_required
@require_GET
def queue(request):
    """The IT queue: active tickets, most urgent first, with simple filters. IT staff only.

    Filters come from the address (?status=OPEN&priority=HIGH&show=mine). Anything that
    isn't a real value is ignored, so a tampered address can't break the page.
    """
    status = request.GET.get("status", "")
    priority = request.GET.get("priority", "")
    show = request.GET.get("show", "")
    if status not in Ticket.Status.values:
        status = ""
    if priority not in Ticket.Priority.values:
        priority = ""
    if show not in ("mine", "unassigned"):
        show = ""

    visible = Ticket.objects.visible_to(request.user)
    tickets = visible.queue(
        status=status,
        priority=priority,
        agent=request.user if show == "mine" else None,
        unassigned_only=show == "unassigned",
    ).with_people()

    counts = visible.status_counts()
    status_tabs = [{"value": value, "label": label, "count": counts[value]} for value, label in Ticket.Status.choices]
    context = {
        "tickets": tickets,
        "status_tabs": status_tabs,
        "status": status,
        "priority": priority,
        "show": show,
        "priority_choices": Ticket.Priority.choices,
    }
    return render(request, "tickets/queue.html", context)
