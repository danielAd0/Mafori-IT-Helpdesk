"""
Admin panel for people (owner: Dan). ADMIN-role users only.

Creating a user here gives them a temporary password, and they must choose
their own at first login (must_change_password is switched on automatically).
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import AdminUserCreationForm, UserChangeForm

from .models import Department, User


class UserCreateForm(AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("email", "first_name", "last_name", "role", "department", "phone_ext")


class UserEditForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserEditForm
    add_form = UserCreateForm

    list_display = (
        "email",
        "first_name",
        "last_name",
        "role",
        "department",
        "is_active",
        "failed_logins",
        "last_login",
    )
    list_filter = ("role", "is_active", "department")
    search_fields = ("email", "first_name", "last_name")
    ordering = ("first_name", "last_name")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Person", {"fields": ("first_name", "last_name", "department", "phone_ext")}),
        ("Access", {"fields": ("role", "is_active", "must_change_password", "failed_logins")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "department",
                    "phone_ext",
                    "password1",
                    "password2",
                ),
                "description": "The password you set here is temporary. They'll be asked to change it when they first log in.",
            },
        ),
    )
    readonly_fields = ("last_login", "date_joined")
    actions = ["unlock_accounts"]

    @admin.action(description="Unlock selected accounts (reset failed logins to 0)")
    def unlock_accounts(self, request, queryset):
        count = queryset.update(failed_logins=0)
        self.message_user(request, f"Unlocked {count} account(s).")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.must_change_password = True
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        # Never delete people: their tickets and history still point at them.
        # Untick "Active" insead when someone leaves.
        return False


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
