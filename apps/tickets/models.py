from django.conf import settings
from django.db import models

from apps.inspections.models import Inspection, InspectionResult


class TicketManager(models.Manager):
    def visible_to(self, user):
        """Return the tickets a given user is permitted to see.

        Inspector  → every ticket.
        Owner      → tickets issued against stores this user owns.
        Anonymous / unknown role → no tickets.

        Mirrors ``InspectionManager.visible_to``.
        """
        if not user.is_authenticated:
            return self.none()
        if user.role == "INSPECTOR":
            return self.all()
        if user.role == "OWNER":
            return self.filter(store__owner=user)
        return self.none()


class Ticket(models.Model):
    """One ticket per failed checklist result (created by Story 9's conduct view).

    The correction deadline lives on the failed ``InspectionResult``.
    """

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

    objects = TicketManager()

    def __str__(self):
        return f"Ticket #{self.pk} — {self.title}"

    @property
    def deadline(self):
        return self.inspection_result.deadline


class EvidenceManager(models.Manager):
    def visible_to(self, user):
        if not user.is_authenticated:
            return self.none()
        if user.role == "INSPECTOR":
            return self.all()
        if user.role == "OWNER":
            return self.filter(ticket__store__owner=user)
        return self.none()


class Evidence(models.Model):
    """A store owner's proof of a fix, attached to one ticket (one violation).

    Append-only (design-notes assumption 4): a re-submission is a new
    row. Only the review fields are written after creation.
    """

    class ReviewStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"

    ticket = models.ForeignKey(
        Ticket,
        on_delete=models.CASCADE,
        related_name="evidence",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
    )
    photo = models.ImageField(upload_to="evidence/%Y/%m/")
    note = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    review_status = models.CharField(
        max_length=16,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
    )
    reviewer_comment = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    objects = EvidenceManager()

    class Meta:
        ordering = ["submitted_at"]
        verbose_name_plural = "evidence"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    review_status__in=["PENDING", "ACCEPTED", "REJECTED"]
                ),
                name="evidence_review_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(review_status="REJECTED")
                | ~models.Q(reviewer_comment=""),
                name="evidence_rejection_has_comment",
            ),
        ]

    def __str__(self):
        return f"Evidence for {self.ticket} ({self.get_review_status_display()})"
