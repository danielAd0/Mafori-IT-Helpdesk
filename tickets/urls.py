from django.urls import path

from . import views

app_name = "tickets"

urlpatterns = [
    path("", views.my_tickets, name="my_tickets"),
    path("new/", views.ticket_create, name="ticket_create"),
    path("<int:pk>/", views.ticket_detail, name="ticket_detail"),
]
