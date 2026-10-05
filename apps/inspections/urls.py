from django.urls import path

from .views import InspectionCreateView

app_name = "inspections"

urlpatterns = [
    path("schedule/", InspectionCreateView.as_view(), name="schedule"),
]
