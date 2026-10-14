from django.urls import path

from .views import OwnerTicketListView

app_name = "tickets"

urlpatterns = [
    path("", OwnerTicketListView.as_view(), name="owner_ticket_list"),
]