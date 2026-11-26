"""Lockout rules for the login system (Milestone 1)."""

from django.contrib.auth import get_user_model

MAX_FAILED_LOGINS = 5
INVALID_MESSAGE = "Invalid email or password."
LOCKED_MESSAGE = "This account is locked. Please contact IT."


def is_locked(email):
    """True when this email's account has used up its failed attempts."""
    User = get_user_model()
    return User.objects.filter(
        email__iexact=(email or "").strip(),
        failed_logins__gte=MAX_FAILED_LOGINS,
    ).exists()
