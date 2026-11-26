"""Login check with lockout.

This is the ONLY authentication backend (see AUTHENTICATION_BACKENDS in the
settings). Because every login goes through it, the Django admin login gets
the same lockout as our own login page. If the stock ModelBackend were also
listed, someone could keep guessing passwords at /admin/login/.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db import transaction

from .lockout import MAX_FAILED_LOGINS


class LockoutBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        email = username.strip().lower()

        # The row lock makes two simultaneous attempts take turns, so the
        # failed-login counter can't be skipped by sending guesses in parallel.
        with transaction.atomic():
            user = User.objects.select_for_update().filter(email__iexact=email).first()

            if user is None:
                # Hash the password anyway, so an unknown email takes as long
                # as a wrong password (same trick as Django's own backend).
                User().set_password(password)
                return None

            # A locked account is not checked against its password at all.
            if user.failed_logins >= MAX_FAILED_LOGINS:
                return None

            if user.check_password(password) and self.user_can_authenticate(user):
                if user.failed_logins:
                    user.failed_logins = 0
                    user.save(update_fields=["failed_logins"])
                return user

            user.failed_logins += 1
            user.save(update_fields=["failed_logins"])
            return None
