"""
Smoke tests for the base layout (owner: Sifiso).

Renders templates/base.html for each kind of visitor without touching the
database, so the layout is checked even before Jack's pages exist.

    python manage.py test tickets.tests.test_templates
"""

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase

from accounts.forms import ChangePasswordForm, LoginForm
from accounts.lockout import INVALID_MESSAGE, LOCKED_MESSAGE
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
        self.assertIn('img/mafori-logo.png" alt="Mafori"', html)
        self.assertIn("IT Helpdesk", html)
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

    def test_browser_tab_icon_is_linked(self):
        self.assertIn("img/favicon-32.png", self.render_for(AnonymousUser()))

    def test_signed_in_pages_use_the_sidebar(self):
        html = self.render_for(self.make_user(User.Role.EMPLOYEE))
        self.assertIn('class="sidebar"', html)
        self.assertIn('aria-controls="sidebar-menu"', html)
        self.assertIn("js/sidebar.js", html)
        self.assertIn('img/mafori-logo.png" alt="Mafori"', html)

    def test_sidebar_links_for_an_employee(self):
        html = self.render_for(self.make_user(User.Role.EMPLOYEE))
        self.assertIn("Dashboard</a>", html)
        self.assertIn("My tickets</a>", html)
        self.assertIn("Log a ticket</a>", html)
        self.assertNotIn("Admin panel", html)

    def test_sign_out_is_a_post_button_in_the_user_menu(self):
        html = self.render_for(self.make_user(User.Role.EMPLOYEE))
        self.assertIn('<details class="user-box">', html)
        self.assertIn('action="/accounts/logout/"', html)
        self.assertIn("csrfmiddlewaretoken", html)
        self.assertIn('href="/accounts/password/change/"', html)

    def test_signed_out_pages_have_no_sidebar(self):
        self.assertNotIn('class="sidebar"', self.render_for(AnonymousUser()))


class LoginPageTests(SimpleTestCase):
    """templates/accounts/login.html with Jack's LoginForm (no database needed)."""

    def render_login(self, error=None, data=None):
        request = RequestFactory().get("/accounts/login/")
        request.user = AnonymousUser()
        form = LoginForm(data) if data is not None else LoginForm()
        context = {"form": form, "error": error, "next": "/tickets/"}
        return render_to_string("accounts/login.html", context, request=request)

    def test_fields_match_jacks_form(self):
        html = self.render_login()
        self.assertIn('name="email"', html)
        self.assertIn('name="password"', html)
        self.assertIn('autocomplete="username"', html)
        self.assertIn('autocomplete="current-password"', html)

    def test_posts_with_csrf_token(self):
        html = self.render_login()
        self.assertIn('method="post"', html)
        self.assertIn("csrfmiddlewaretoken", html)

    def test_keeps_next_page(self):
        self.assertIn('name="next" value="/tickets/"', self.render_login())

    def test_shows_the_views_error_messages(self):
        self.assertIn(INVALID_MESSAGE, self.render_login(error=INVALID_MESSAGE))
        self.assertIn(LOCKED_MESSAGE, self.render_login(error=LOCKED_MESSAGE))

    def test_shows_field_errors(self):
        html = self.render_login(data={"email": "not-an-email", "password": ""})
        self.assertIn('id="email-error"', html)
        self.assertIn('id="password-error"', html)

    def test_typed_email_is_kept_and_escaped(self):
        html = self.render_login(data={"email": '"><script>x</script>', "password": "x"})
        self.assertNotIn("<script>x</script>", html)

    def test_no_self_sign_up(self):
        # Accounts are created by an admin, never by visitors
        self.assertNotIn("sign up", self.render_login().lower())

    def test_show_password_button_is_hidden_without_javascript(self):
        html = self.render_login()
        self.assertIn('data-password-toggle="id_password"', html)
        self.assertIn("js/password-toggle.js", html)

    def test_shows_logo_with_alt_text(self):
        self.assertIn('img/mafori-logo.png" alt="Mafori"', self.render_login())


class ChangePasswordPageTests(SimpleTestCase):
    """templates/accounts/change_password.html with Jack's ChangePasswordForm."""

    def render_page(self, forced=False):
        user = User(email="thandi@maforigroup.co.za", first_name="Thandi", role=User.Role.EMPLOYEE)
        request = RequestFactory().get("/accounts/password/change/")
        request.user = user
        context = {"form": ChangePasswordForm(user), "forced": forced}
        return render_to_string("accounts/change_password.html", context, request=request)

    def test_fields_match_jacks_form(self):
        html = self.render_page()
        for name in ("old_password", "new_password1", "new_password2"):
            self.assertIn(f'name="{name}"', html)
        self.assertEqual(html.count('autocomplete="new-password"'), 2)

    def test_forced_change_explains_why(self):
        html = self.render_page(forced=True)
        self.assertIn("temporary password", html)
        self.assertNotIn("Back to the helpdesk", html)

    def test_normal_change_offers_a_way_back(self):
        self.assertIn("Back to the helpdesk", self.render_page())

    def test_shows_the_password_rules(self):
        self.assertIn('id="new-rules"', self.render_page())

    def test_sign_out_is_a_post_button(self):
        html = self.render_page(forced=True)
        self.assertIn('action="/accounts/logout/"', html)
        self.assertIn("csrfmiddlewaretoken", html)
