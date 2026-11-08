from django.urls import path

from .views import InspectionConductView, InspectionCreateView, InspectionSubmitView

app_name = "inspections"

urlpatterns = [
    path("schedule/", InspectionCreateView.as_view(), name="schedule"),
    path("<int:pk>/conduct/", InspectionConductView.as_view(), name="conduct"),
    path("<int:pk>/submit/", InspectionSubmitView.as_view(), name="submit"),
]
