from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from apps.common.mixins import InspectorRequiredMixin

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
