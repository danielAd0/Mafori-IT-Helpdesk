from django import forms
from django.contrib.auth.forms import PasswordChangeForm


class LoginForm(forms.Form):
    email = forms.EmailField(
        max_length=254,
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )

    password = forms.CharField(
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class ChangePasswordForm(PasswordChangeForm):
    """Django's password change form, plus two rules from the plan:
    the new password must differ from the current (temporary) one, and
    saving clears must_change_password.

    Length (8+), common-password and similar-to-email checks come from
    AUTH_PASSWORD_VALIDATORS in the settings.
    """

    def clean_new_password1(self):
        password = self.cleaned_data.get("new_password1")
        if password and self.user.check_password(password):
            raise forms.ValidationError(
                "Your new password must be different from your current one.",
                code="password_unchanged",
            )
        return password

    def save(self, commit=True):
        self.user.must_change_password = False
        return super().save(commit=commit)
