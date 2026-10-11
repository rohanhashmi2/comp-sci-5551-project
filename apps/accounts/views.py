from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as BaseLoginView
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import CreateView, RedirectView, TemplateView

from apps.inspections.models import Inspection
from apps.stores.models import Store

from .forms import EmailAuthenticationForm, RegistrationForm
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


class LoginView(BaseLoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class HomeView(RedirectView):
    permanent = False

    def get_redirect_url(self, *args, **kwargs):
        if not self.request.user.is_authenticated:
            return reverse("accounts:login")
        if self.request.user.role == User.Role.INSPECTOR:
            return reverse("accounts:inspector_dashboard")
        return reverse("accounts:owner_dashboard")


class InspectorDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard_inspector.html"

    def dispatch(self, request, *args, **kwargs):
        # Inline role guard — replaced by Track C's InspectorRequiredMixin
        # once common.mixins exists.
        if request.user.is_authenticated and request.user.role != User.Role.INSPECTOR:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["inspections"] = Inspection.objects.visible_to(self.request.user)
        return ctx


class OwnerDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "accounts/dashboard_owner.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.role != User.Role.OWNER:
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["stores"] = Store.objects.visible_to(self.request.user)
        return ctx
