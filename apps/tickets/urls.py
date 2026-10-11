from django.urls import path

from .views import EvidenceCreateView, EvidenceReviewView, TicketDetailView

app_name = "tickets"

urlpatterns = [
    path("<int:pk>/", TicketDetailView.as_view(), name="detail"),
    path(
        "violations/<int:result_pk>/evidence/",
        EvidenceCreateView.as_view(),
        name="evidence_create",
    ),
    path(
        "evidence/<int:pk>/review/",
        EvidenceReviewView.as_view(),
        name="evidence_review",
    ),
]
