from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import Department, User


class UserModelTests(TestCase):
    def test_email_is_the_login_and_stored_lowercase(self):
        user = User.objects.create_user(
            "  Thandi.Mokoena@MaforiGroup.co.za ", "Pass-word-123", first_name="Thandi", last_name="Mokoena"
        )
        self.assertEqual(user.email, "thandi.mokoena@maforigroup.co.za")
        self.assertTrue(user.check_password("Pass-word-123"))

    def test_login_lookup_ignores_letter_case(self):
        User.objects.create_user("thandi@maforigroup.co.za", "Pass-word-123")
        found = User.objects.get_by_natural_key("THANDI@maforigroup.CO.ZA")
        self.assertEqual(found.email, "thandi@maforigroup.co.za")

    def test_two_accounts_cannot_differ_only_by_case(self):
        User.objects.create_user("thandi@maforigroup.co.za", "Pass-word-123")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("THANDI@maforigroup.co.za", "Pass-word-123")

    def test_password_is_hashed_not_stored(self):
        user = User.objects.create_user("a@maforigroup.co.za", "Pass-word-123")
        self.assertNotIn("Pass-word-123", user.password)
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))

    def test_only_admin_role_gets_admin_panel_access(self):
        employee = User.objects.create_user("e@maforigroup.co.za", "x")
        agent = User.objects.create_user("g@maforigroup.co.za", "x", role=User.Role.AGENT)
        admin = User.objects.create_user("d@maforigroup.co.za", "x", role=User.Role.ADMIN)
        self.assertFalse(employee.is_staff)
        self.assertFalse(agent.is_staff)
        self.assertTrue(admin.is_staff)

    def test_is_staff_cannot_be_set_by_hand(self):
        employee = User.objects.create_user("e@maforigroup.co.za", "x")
        employee.is_staff = True
        employee.save()
        employee.refresh_from_db()
        self.assertFalse(employee.is_staff)

    def test_is_it_staff(self):
        self.assertFalse(User.objects.create_user("e@maforigroup.co.za", "x").is_it_staff)
        self.assertTrue(User.objects.create_user("g@maforigroup.co.za", "x", role=User.Role.AGENT).is_it_staff)
        gone = User.objects.create_user("old@maforigroup.co.za", "x", role=User.Role.AGENT, is_active=False)
        self.assertFalse(gone.is_it_staff)

    def test_superuser_is_always_admin(self):
        su = User.objects.create_superuser("boss@maforigroup.co.za", "Pass-word-123")
        self.assertEqual(su.role, User.Role.ADMIN)
        self.assertTrue(su.is_staff)
        with self.assertRaises(ValueError):
            User.objects.create_superuser("x@maforigroup.co.za", "Pass-word-123", role=User.Role.EMPLOYEE)

    def test_database_rejects_unknown_role(self):
        user = User.objects.create_user("e@maforigroup.co.za", "x")
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=user.pk).update(role="BOSS")

    def test_department_in_use_cannot_be_deleted(self):
        finance = Department.objects.create(name="Finance")
        User.objects.create_user("e@maforigroup.co.za", "x", department=finance)
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            finance.delete()
