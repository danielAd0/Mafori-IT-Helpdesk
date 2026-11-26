from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods, require_POST

from .forms import ChangePasswordForm, LoginForm
from .lockout import INVALID_MESSAGE, LOCKED_MESSAGE, is_locked


def _safe_next(request):
    """Where to go after login: the page they asked for, if it is in this site."""
    target = request.POST.get("next") or request.GET.get("next") or ""
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return settings.LOGIN_REDIRECT_URL


@login_not_required
@require_http_methods(["GET", "POST"])
@sensitive_post_parameters("password")
def login_view(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    error = None
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            user = authenticate(request, username=email, password=form.cleaned_data["password"])
            if user is not None:
                login(request, user)  # starts a new session key (blocks fixation)
                if user.must_change_password:
                    return redirect("accounts:change_password")
                return redirect(_safe_next(request))
            # Same message for a wrong email and a wrong password.
            error = LOCKED_MESSAGE if is_locked(email) else INVALID_MESSAGE
    else:
        form = LoginForm()

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "error": error,
            "next": request.POST.get("next") or request.GET.get("next", ""),
        },
    )


@require_POST  # logging out is a button (POST), never a link
def logout_view(request):
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


@sensitive_post_parameters("old_password", "new_password1", "new_password2")
def change_password_view(request):
    if request.method == "POST":
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # stay logged in
            messages.success(request, "Your password has been changed.")
            return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = ChangePasswordForm(request.user)

    return render(
        request,
        "accounts/change_password.html",
        {"form": form, "forced": request.user.must_change_password},
    )
