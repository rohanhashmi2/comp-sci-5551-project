from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import CreateView, TemplateView

from .forms import RegistrationForm
from .models import User


class RegisterView(CreateView):
    model = User
    form_class = RegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:register_done")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Your account is ready to use.")
        return response


class RegistrationDoneView(TemplateView):
    template_name = "accounts/register_done.html"
