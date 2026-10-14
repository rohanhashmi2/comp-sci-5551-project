from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView

from .models import Ticket


class OwnerTicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "tickets/owner_ticket_list.html"
    context_object_name = "tickets"

    def get_queryset(self):
        return Ticket.objects.filter(
            store__owner=self.request.user,
            status=Ticket.Status.OPEN,
        )