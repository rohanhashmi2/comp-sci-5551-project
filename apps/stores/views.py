from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch, Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView

from apps.common.mixins import InspectorRequiredMixin
from apps.inspections.models import Inspection, InspectionResult
from apps.tickets.models import Ticket

from .forms import StoreForm
from .models import Store


class StoreListView(LoginRequiredMixin, InspectorRequiredMixin, ListView):
    model = Store
    template_name = "stores/store_list.html"
    context_object_name = "stores"

    def get_queryset(self):
        return Store.objects.visible_to(self.request.user)


class StoreCreateView(LoginRequiredMixin, InspectorRequiredMixin, CreateView):
    model = Store
    form_class = StoreForm
    template_name = "stores/store_form.html"
    success_url = reverse_lazy("stores:list")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Store '{form.instance.name}' created.")
        return response


class StoreHistoryView(LoginRequiredMixin, DetailView):
    """Recorded inspections of one store, oldest first, with their tickets.

    An inspection is part of the history once its checklist is recorded,
    i.e. any status after SCHEDULED. Open to both roles. The store is
    looked up through ``visible_to``, so an owner requesting another
    owner's store gets a 404.
    """

    template_name = "stores/store_history.html"
    context_object_name = "store"

    def get_queryset(self):
        return Store.objects.visible_to(self.request.user)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["inspections"] = (
            self.object.inspections.exclude(status=Inspection.Status.SCHEDULED)
            .prefetch_related(
                Prefetch("tickets", queryset=Ticket.objects.order_by("pk"))
            )
            .annotate(
                violation_count=Count(
                    "results",
                    filter=Q(results__outcome=InspectionResult.Outcome.FAIL),
                )
            )
            .order_by("scheduled_for")
        )
        return ctx
