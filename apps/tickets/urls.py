from django.urls import path

from .views import (
    EvidenceCreateView,
    EvidenceReviewQueueView,
    EvidenceReviewView,
    OwnerTicketListView,
    TicketDetailView,
)

app_name = "tickets"

urlpatterns = [
    path("", OwnerTicketListView.as_view(), name="owner_ticket_list"),
    path("review/", EvidenceReviewQueueView.as_view(), name="review_queue"),
    path("<int:pk>/", TicketDetailView.as_view(), name="detail"),
    path("<int:pk>/evidence/", EvidenceCreateView.as_view(), name="evidence_create"),
    path(
        "evidence/<int:pk>/review/",
        EvidenceReviewView.as_view(),
        name="evidence_review",
    ),
]
