from django.db import models

from apps.inspections.models import Inspection, InspectionResult

class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        IN_PROGRESS = "IN_PROGRESS", "In Progress"
        RESOLVED = "RESOLVED", "Resolved"
        CLOSED = "CLOSED", "Closed"

    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.CASCADE,
        related_name="tickets",
    )

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.CASCADE,
    )

    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="created_tickets",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    title = models.CharField(max_length=200)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    inspection_result = models.OneToOneField(
        InspectionResult,
        on_delete=models.CASCADE,
        related_name="ticket",
    )