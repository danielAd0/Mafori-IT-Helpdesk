from django.test import TestCase

from accounts.models import User


class AdminPasswordResetTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin@maforigroup.co.za", "Admin-Pass-123", role=User.Role.ADMIN)
        self.staff = User.objects.create_user("staff@maforigroup.co.za", "Old-Pass-123", failed_logins=5)
        self.client.force_login(self.admin)

    def test_reset_by_admin_is_temporary_and_unlocks(self):
        url = f"/admin/accounts/user/{self.staff.pk}/password/"
        response = self.client.post(
            url, {"password1": "Temp-Reset-4821", "password2": "Temp-Reset-4821", "usable_password": "true"}
        )
        self.assertEqual(response.status_code, 302)
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password("Temp-Reset-4821"))
        self.assertTrue(self.staff.must_change_password)
        self.assertEqual(self.staff.failed_logins, 0)

    def test_new_user_from_admin_must_change_password(self):
        self.client.post(
            "/admin/accounts/user/add/",
            {
                "email": "New.Starter@maforigroup.co.za",
                "first_name": "New",
                "last_name": "Starter",
                "role": "EMPLOYEE",
                "password1": "Temp-Pass-0193",
                "password2": "Temp-Pass-0193",
                "usable_password": "true",
            },
        )
        user = User.objects.get(email="new.starter@maforigroup.co.za")
        self.assertTrue(user.must_change_password)
        self.assertFalse(user.is_staff)

    def test_agent_cannot_open_admin(self):
        agent = User.objects.create_user("agent@maforigroup.co.za", "x", role=User.Role.AGENT)
        self.client.force_login(agent)
        self.assertEqual(self.client.get("/admin/accounts/user/").status_code, 302)
