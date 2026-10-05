from django.urls import path

from .views import StoreCreateView, StoreListView

app_name = "stores"

urlpatterns = [
    path("", StoreListView.as_view(), name="list"),
    path("add/", StoreCreateView.as_view(), name="add"),
]
