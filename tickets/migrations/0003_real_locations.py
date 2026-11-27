"""
Replace the starter placeholders with Mafori's real branch list (written by Jack, for Dan to review).

- Every location in REAL_LOCATIONS is created if it is missing and put in this order
  ("Other" always last). Whether a location is active is never changed here, so admin
  edits are not overwritten.
- The old placeholder offices are switched off, not deleted, because tickets may already
  point at them (a ticket's location is protected from deletion).
"""

from django.db import migrations

REAL_LOCATIONS = [
    "Bloemfontein",
    "Centurion",
    "George",
    "Groblersdal",
    "Kimberly",
    "King William's Town",
    "Kronstad",
    "Lynnwood Headquaters",
    "Maluti-A-Phufong",
    "Makhado",
    "Mokopane",
    "Phalaborwa",
    "Polokwane",
    "Pretorius",
    "Pretoria North",
    "Sunnyside",
    "Thohoyandou",
    "Tzaneen",
    "Witbank",
    "Zwelitsha",
    "Other",
]

RETIRED_PLACEHOLDERS = [
    "Head office - Ground floor",
    "Head office - 1st floor",
    "Head office - 2nd floor",
    "Boardroom",
    "Reception",
    "Remote (working from home)",
]


def use_real_locations(apps, schema_editor):
    Location = apps.get_model("tickets", "Location")
    for position, name in enumerate(REAL_LOCATIONS, start=1):
        sort_order = 1000 if name == "Other" else position * 10
        location = Location.objects.filter(name__iexact=name).first()
        if location is None:
            Location.objects.create(name=name, sort_order=sort_order)
        else:
            location.sort_order = sort_order
            location.save(update_fields=["sort_order"])
        Location.objects.filter(name__in=RETIRED_PLACEHOLDERS).update(is_active=False, sort_order=5000)


class Migration(migrations.Migration):
    dependencies = [
        ("tickets", "0002_location"),
    ]

    operations = [
        migrations.RunPython(use_real_locations, migrations.RunPython.noop),
    ]