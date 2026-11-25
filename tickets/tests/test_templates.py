"""
Smoke tests for the base layout (owner: Sifiso).

Renders templates/base.html for each kind of visitor without touching the
database, so the layout is checked even before Jack's pages exist.

    python manage.py test tickets.tests.test_templates
"""

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from accounts.models import User


class BaseLayoutTests(SimpleTestCase):
    def render_for(self, user):
        request = RequestFactory().get("/")
        request.user = user
        return render_to_string("base.html", request=request)

    def make_user(self, role, first_name="Thandi"):
        # Not saved: rendering must not need the database
        return User(email="thandi@maforigroup.co.za", first_name=first_name, role=role)

    def test_logged_out_visitor_sees_no_menu(self):
        html = self.render_for(AnonymousUser())
        self.assertIn("Mafori IT Helpdesk", html)
        self.assertIn('href="#main"', html)  # skip link for keyboard users
        self.assertNotIn('aria-label="Main"', html)

    def test_employee_sees_name_and_role_but_no_admin_link(self):
        html = self.render_for(self.make_user(User.Role.EMPLOYEE))
        self.assertIn("Thandi", html)
        self.assertIn("Employee", html)
        self.assertNotIn("/admin/", html)

    def test_admin_sees_admin_link(self):
        html = self.render_for(self.make_user(User.Role.ADMIN))
        self.assertIn('href="/admin/"', html)

    def test_user_text_is_escaped(self):
        html = self.render_for(self.make_user(User.Role.EMPLOYEE, first_name="<script>x</script>"))
        self.assertNotIn("<script>x</script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_stylesheet_is_linked(self):
        html = self.render_for(AnonymousUser())
        self.assertIn("css/mafori.css", html)
