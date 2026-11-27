"""Role checks for views (owner: Jack).

Hiding a link is not protection. A view that only IT staff may use must say so
here, so an employee who types the address gets a 403 instead of the page.
"""

from functools import wraps

from django.core.exceptions import PermissionDenied


def it_staff_required(view):
    """Only active agents and admins may use this view; everyone gets a 403."""

    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not getattr(request.user, "is_it_staff", False):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
