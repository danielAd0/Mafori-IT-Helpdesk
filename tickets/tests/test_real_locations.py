"""The migration leaves the real branch list in the database."""

from django.test import TestCase

from tickets.models import Location


class RealLocationsTests(TestCase):
    def test_real_branches_exist_and_are_active(self):
        for name in ["Bloemfontein", "Polokwane", "Pretoria North", "Witbank", "Other"]:
            self.assertTrue(Location.objects.filter(name=name, is_active=True).exists(), name)

    def test_the_old_placeholders_are_retired(self):
        placeholder = Location.objects.get(name="Head office - Ground floor")
        self.assertFalse(placeholder.is_active)

    def test_other_comes_last_among_active_locations(self):
        active = list(Location.objects.filter(is_active=True))
        self.assertEqual(active[-1].name, "Other")
