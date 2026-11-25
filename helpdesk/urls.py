"""Root URLs. Jack adds the app's pages here as each miletone lands."""

from django.contrib import admin
from django.urls import path

admin.site.site_header = "Mafori IT Helpdesk admin"
admin.site.site_title = "Mafori IT Helpdesk"
admin.site.index_title = "Manage users, departments and categories"

urlpatterns = [
    path("admin/", admin.site.urls),
]
