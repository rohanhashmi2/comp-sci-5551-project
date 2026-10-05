from django.contrib.auth import views as auth_views
from django.urls import path

from .views import (
    InspectorDashboardView,
    LoginView,
    OwnerDashboardView,
    RegisterView,
    RegistrationDoneView,
)

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("register/done/", RegistrationDoneView.as_view(), name="register_done"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("inspector/", InspectorDashboardView.as_view(), name="inspector_dashboard"),
    path("owner/", OwnerDashboardView.as_view(), name="owner_dashboard"),
]
