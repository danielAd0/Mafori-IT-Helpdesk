"""
Load the starting departments and categories (owner: Dan).

    python manage.py seed_reference_data

Runs on every deploy (build.sh). Each list is only filled when it's empty, so
once admins start renaming or retiring entries in the admin panel,
a deploy never puts the old values back. (Plain "loaddata initial_data" would
overwrite them every time.) Locations get their starter list from migration
tickets/0002_location instead.
"""

import json
from pathlib import Path

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "initial_data.json"


class Command(BaseCommand):
    help = "Fill the department and category lists, but only the ones that are still empty."

    def handle(self, *args, **options):
        rows = json.loads(FIXTURE.read_text(encoding="utf-8"))
        by_model = {}
        for row in rows:
            by_model.setdefault(row["model"], []).append(row)

        with transaction.atomic():
            for label, model_rows in by_model.items():
                model = apps.get_model(label)
                name = model._meta.verbose_name_plural
                if model.objects.exists():
                    self.stdout.write(f"{name}: already set up, left alone")
                    continue
                model.objects.bulk_create(model(**row["fields"]) for row in model_rows)
                self.stdout.write(f"{name}: added {len(model_rows)}")
