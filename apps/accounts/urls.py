from django.urls import path

from .views import RegisterView, RegistrationDoneView

app_name = "accounts"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("register/done/", RegistrationDoneView.as_view(), name="register_done"),
]
