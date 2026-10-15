from django.urls import path

from .views import StoreCreateView, StoreHistoryView, StoreListView

app_name = "stores"

urlpatterns = [
    path("", StoreListView.as_view(), name="list"),
    path("add/", StoreCreateView.as_view(), name="add"),
    path("<int:pk>/history/", StoreHistoryView.as_view(), name="history"),
]
