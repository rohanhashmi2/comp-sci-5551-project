from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView

from apps.common.mixins import InspectorRequiredMixin

from .forms import InspectionScheduleForm
from .models import Inspection


class InspectionCreateView(LoginRequiredMixin, InspectorRequiredMixin, CreateView):
    model = Inspection
    form_class = InspectionScheduleForm
    template_name = "inspections/inspection_form.html"
    success_url = reverse_lazy("accounts:inspector_dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Inspection scheduled for {form.instance.store.name}.",
        )
        return response
