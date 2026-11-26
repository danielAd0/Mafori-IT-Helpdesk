"""
Location becomes a list managed in the admin panel instead of free text (owner: Dan).

Steps, so no ticket loses the location it already has:
  1. create the Location table and fill it with a starter list
     (placeholders until Mafori gives us their real offices; edit them in the admin)
  2. keep the old text in a temporary column (location_text)
  3. add the new location link
  4. turn each different text value into a Location and link the tickets to it
  5. drop the temporary column

The starter list is added here, not on every deploy, so it goes in exactly once
per database and admin edits are never overwritten.
"""

import django.db.models.deletion
from django.db import migrations, models


STARTER_LOCATIONS = [
    "Head office - Ground floor",
    "Head office - 1st floor",
    "Head office - 2nd floor",
    "Boardroom",
    "Reception",
    "Remote (working from home)",
    "Other",
]


def add_starter_locations(apps, schema_editor):
    Location = apps.get_model("tickets", "Location")
    for i, name in enumerate(STARTER_LOCATIONS, start=1):
        Location.objects.get_or_create(name=name, defaults={"sort_order": i * 10})


def text_to_locations(apps, schema_editor):
    Location = apps.get_model("tickets", "Location")
    Ticket = apps.get_model("tickets", "Ticket")
    by_name = {}
    for ticket in Ticket.objects.exclude(location_text="").order_by("id").only("id", "location_text"):
        name = " ".join(ticket.location_text.split())  # trim and squash double spaces; the oldest spelling wins
        if not name:
            continue
        key = name.lower()  # "Floor 2" and "floor 2" end up as one location
        if key not in by_name:
            by_name[key] = Location.objects.filter(name__iexact=name).first() or Location.objects.create(
                name=name, sort_order=100
            )
        Ticket.objects.filter(pk=ticket.pk).update(location=by_name[key])


def locations_to_text(apps, schema_editor):
    Ticket = apps.get_model("tickets", "Ticket")
    for ticket in Ticket.objects.filter(location__isnull=False).select_related("location"):
        Ticket.objects.filter(pk=ticket.pk).update(location_text=ticket.location.name)


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Location",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                (
                    "is_active",
                    models.BooleanField(default=True, help_text="Untick to stop it appearing in the ticket form."),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(
                        default=0,
                        help_text="Lower numbers come first in the dropdown. Equal numbers are sorted by name.",
                    ),
                ),
            ],
            options={"ordering": ["sort_order", "name"]},
        ),
        migrations.RunPython(add_starter_locations, migrations.RunPython.noop),
        migrations.RenameField(model_name="ticket", old_name="location", new_name="location_text"),
        migrations.AddField(
            model_name="ticket",
            name="location",
            field=models.ForeignKey(
                blank=True,
                help_text="Office or floor",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tickets",
                to="tickets.location",
            ),
        ),
        migrations.RunPython(text_to_locations, locations_to_text),
        migrations.RemoveField(model_name="ticket", name="location_text"),
    ]
