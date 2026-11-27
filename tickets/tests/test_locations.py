from io import StringIO

from django.contrib.admin.sites import site
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.db.models import ProtectedError
from django.test import RequestFactory, TestCase, TransactionTestCase

from accounts.models import Department, User
from tickets.models import Category, Location, Ticket


class LocationModelTests(TestCase):
    def test_migration_adds_a_starter_list(self):
        names = list(Location.objects.values_list("name", flat=True))
        self.assertEqual(names[0], "Bloemfontein")
        self.assertIn("Remote (working from home)", names)

    def test_dropdown_order_is_sort_order_then_name(self):
        Location.objects.all().delete()
        Location.objects.create(name="Zebra room", sort_order=1)
        Location.objects.create(name="Boardroom", sort_order=2)
        Location.objects.create(name="Annex", sort_order=2)
        self.assertEqual(
            list(Location.objects.values_list("name", flat=True)),
            ["Zebra room", "Annex", "Boardroom"],
        )

    def test_names_are_unique(self):
        Location.objects.create(name="Server room")
        with self.assertRaises(IntegrityError), transaction.atomic():
            Location.objects.create(name="Server room")

    def test_new_locations_are_active_with_sort_order_zero(self):
        loc = Location.objects.create(name="Warehouse")
        self.assertTrue(loc.is_active)
        self.assertEqual(loc.sort_order, 0)
        self.assertEqual(str(loc), "Warehouse")

    def test_a_location_in_use_cannot_be_deleted(self):
        loc = Location.objects.get(name="Reception")
        user = User.objects.create_user("staff@maforigroup.co.za", "x")
        Ticket.objects.create(
            subject="Phone dead",
            description="No dial tone",
            category=Category.objects.create(name="Phones"),
            requester=user,
            location=loc,
        )
        with self.assertRaises(ProtectedError):
            loc.delete()

    def test_location_is_optional_on_a_ticket(self):
        user = User.objects.create_user("staff@maforigroup.co.za", "x")
        ticket = Ticket.objects.create(
            subject="Slow PC",
            description="Very slow",
            category=Category.objects.create(name="Hardware"),
            requester=user,
        )
        self.assertIsNone(ticket.location)


class LocationAdminTests(TestCase):
    def test_registered_and_cannot_be_deleted(self):
        self.assertIn(Location, site._registry)
        admin = User.objects.create_user("admin@maforigroup.co.za", "x", role=User.Role.ADMIN)
        request = RequestFactory().get("/admin/")
        request.user = admin
        model_admin = site._registry[Location]
        self.assertTrue(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request))


class SeedReferenceDataTests(TestCase):
    def run_command(self):
        out = StringIO()
        call_command("seed_reference_data", stdout=out)
        return out.getvalue()

    def test_fills_empty_lists(self):
        self.run_command()
        self.assertTrue(Department.objects.filter(name="Finance").exists())
        self.assertTrue(Category.objects.filter(name="Hardware").exists())

    def test_running_twice_adds_nothing_new(self):
        self.run_command()
        counts = (Department.objects.count(), Category.objects.count())
        output = self.run_command()
        self.assertEqual(counts, (Department.objects.count(), Category.objects.count()))
        self.assertIn("left alone", output)

    def test_admin_edits_survive_a_deploy(self):
        self.run_command()
        hardware = Category.objects.get(name="Hardware")
        hardware.name = "Computers"
        hardware.is_active = False
        hardware.save()
        self.run_command()
        hardware.refresh_from_db()
        self.assertEqual(hardware.name, "Computers")
        self.assertFalse(hardware.is_active)
        self.assertFalse(Category.objects.filter(name="Hardware").exists())


class LocationMigrationTests(TransactionTestCase):
    """Old free-text locations become Location rows, and no ticket loses its location."""

    before = [("tickets", "0001_initial"), ("accounts", "0002_user_failed_logins")]
    after = [("tickets", "0002_location")]

    def setUp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.before)
        old = executor.loader.project_state(self.before).apps
        OldUser = old.get_model("accounts", "User")
        OldCategory = old.get_model("tickets", "Category")
        OldTicket = old.get_model("tickets", "Ticket")
        user = OldUser.objects.create(email="staff@maforigroup.co.za", password="x", role="EMPLOYEE")
        cat = OldCategory.objects.create(name="Hardware")
        for text in ["Floor 2", "floor  2 ", "Reception", ""]:
            OldTicket.objects.create(
                subject=text or "none", description="d", category=cat, requester=user, location=text
            )

        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(self.after)
        self.apps = executor.loader.project_state(self.after).apps

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())

    def test_text_becomes_locations(self):
        NewLocation = self.apps.get_model("tickets", "Location")
        NewTicket = self.apps.get_model("tickets", "Ticket")
        names = set(NewLocation.objects.values_list("name", flat=True))
        self.assertIn("Floor 2", names)
        self.assertNotIn("floor 2", names)  # same place, different spelling: merged
        self.assertEqual(NewLocation.objects.filter(name="Reception").count(), 1)  # matched the starter one
        floor2 = NewLocation.objects.get(name="Floor 2")
        self.assertEqual(NewTicket.objects.get(subject="Reception").location.name, "Reception")
        self.assertEqual(NewTicket.objects.filter(location=floor2).count(), 2)
        self.assertIsNone(NewTicket.objects.get(subject="none").location_id)
