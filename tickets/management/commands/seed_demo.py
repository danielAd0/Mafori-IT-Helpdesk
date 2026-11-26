"""
Demo data for local development (owner: Dan).

    python manage.py seed_demo

Creates three test logins and a few sample tickets so pages have something
to show. Safe to run more than once. Refuses to run unless DEBUG is on, so it
can never put test accounts on the live site.

Test logins (local only):
    admin@maforigroup.co.za     Admin@2026   ADMIN
    it.agent@maforigroup.co.za  Agent@2026   AGENT
    staff@maforigroup.co.za     Staff@2026   EMPLOYEE
"""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Department, User
from tickets.models import Category, Location, Ticket, TicketComment, TicketHistory

DEMO_USERS = [
    ("admin@maforigroup.co.za", "Admin@2026", "System", "Admin", User.Role.ADMIN, "IT"),
    ("it.agent@maforigroup.co.za", "Agent@2026", "IT", "Agent", User.Role.AGENT, "IT"),
    ("staff@maforigroup.co.za", "Staff@2026", "Test", "Staff", User.Role.EMPLOYEE, "Finance"),
]


class Command(BaseCommand):
    help = "Load test users and sample tickets for local development (DEBUG only)."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_demo only runs with DJANGO_DEBUG=True. It must never touch the live site.")

        if not Category.objects.exists():
            call_command("loaddata", "initial_data", verbosity=0)

        users = {}
        for email, password, first, last, role, dept in DEMO_USERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": role,
                    "department": Department.objects.get(name=dept),
                },
            )
            if created:
                user.set_password(password)
                if role == User.Role.ADMIN:
                    user.is_superuser = True
                user.save()
            users[role] = user

        if Ticket.objects.exists():
            self.stdout.write("Tickets already exist, so no sample tickets were added.")
        else:
            staff, agent, admin = users[User.Role.EMPLOYEE], users[User.Role.AGENT], users[User.Role.ADMIN]
            first_floor, _ = Location.objects.get_or_create(name="Head office - 1st floor")
            second_floor, _ = Location.objects.get_or_create(name="Head office - 2nd floor")
            laptop = Ticket.objects.create(
                subject="Laptop will not boot",
                description="Black screen after the Windows logo since this morning.",
                category=Category.objects.get(name="Hardware"),
                priority=Ticket.Priority.HIGH,
                status=Ticket.Status.ASSIGNED,
                requester=staff,
                assigned_to=agent,
                asset_tag="MAF-LT-014",
                location=first_floor,
            )
            Ticket.objects.create(
                subject="Need Excel licence",
                description="New starter in Finance needs Microsoft Excel.",
                category=Category.objects.get(name="Software"),
                requester=staff,
                location=first_floor,
            )
            printer = Ticket.objects.create(
                subject="Printer jamming",
                description="Second floor printer jams on every double-sided job.",
                category=Category.objects.get(name="Printing"),
                priority=Ticket.Priority.LOW,
                status=Ticket.Status.IN_PROGRESS,
                requester=staff,
                assigned_to=agent,
                asset_tag="MAF-PR-002",
                location=second_floor,
            )
            TicketComment.objects.create(
                ticket=laptop, author=agent, body="Collecting the laptop at 11:00 to check the drive."
            )
            TicketComment.objects.create(
                ticket=laptop,
                author=agent,
                body="Suspect SSD failure - check warranty before replacing.",
                is_internal=True,
            )
            TicketHistory.objects.create(
                ticket=laptop, changed_by=admin, field="ASSIGNED_TO", old_value="", new_value=agent.email
            )
            TicketHistory.objects.create(
                ticket=laptop, changed_by=admin, field="STATUS", old_value="OPEN", new_value="ASSIGNED"
            )
            TicketHistory.objects.create(
                ticket=printer, changed_by=agent, field="STATUS", old_value="ASSIGNED", new_value="IN_PROGRESS"
            )

        self.stdout.write(
            self.style.SUCCESS("Demo data ready. Log in at /admin/ with admin@maforigroup.co.za / Admin@2026")
        )
