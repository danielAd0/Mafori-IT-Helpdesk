"""Middleware for the login system (Milestone 1)."""

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.cache import add_never_cache_headers


class ForcePasswordChangeMiddleware:
    """Send anyone on a temporary password to the change-password page.

    Until must_change_password is cleared, the only pages they can reach are
    the change-password page and logout.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if user.is_authenticated and getattr(user, "must_change_password", False):
            allowed = {
                reverse("accounts:change_password"),
                reverse("accounts:logout"),
            }
            if request.path not in allowed:
                return redirect("accounts:change_password")
        return self.get_response(request)


class NoCacheMiddleware:
    """Stop the browser caching pages shown to logged-in users.

    After logout, the Back button must not show a cached private page.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            add_never_cache_headers(response)
        return response
