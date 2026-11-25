"""
Admin panel for tickets (owner: Dan). ADMIN-role users only.

Status, priority, category and assignee are read-only here on purpose: changes
made in the admin panel would skip the ticket history, so they're made through
the app's own pages, which record every change.
"""

from django.contrib import admin

from .models import Category, Ticket, TicketComment, TicketHistory


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "is_active")
    list_editable = ("is_active",)
    search_fields = ("name",)

    def has_delete_permission(self, request, obj=None):
        # Old tickets keep their category. Untick "Active" to retire one.
        return False


class CommentInline(admin.TabularInline):
    model = TicketComment
    extra = 0
    fields = ("created_at", "author", "is_internal", "body")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class HistoryInline(admin.TabularInline):
    model = TicketHistory
    extra = 0
    fields = ("changed_at", "changed_by", "field", "old_value", "new_value")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "subject", "status", "priority", "category", "requester", "assigned_to", "created_at")
    list_filter = ("status", "priority", "category")
    search_fields = ("subject", "description", "requester__email", "requester__first_name", "requester__last_name")
    list_select_related = ("category", "requester", "assigned_to")
    readonly_fields = (
        "reference",
        "status",
        "priority",
        "category",
        "requester",
        "assigned_to",
        "created_at",
        "updated_at",
        "resolved_at",
        "closed_at",
    )
    inlines = [CommentInline, HistoryInline]

    @admin.display(description="Reference", ordering="id")
    def reference(self, obj):
        return obj.reference

    def has_add_permission(self, request):
        return False  # tickets are logged through the app

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TicketHistory)
class TicketHistoryAdmin(admin.ModelAdmin):
    list_display = ("ticket", "field", "old_value", "new_value", "changed_by", "changed_at")
    list_filter = ("field",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
