from django.conf import settings
from django.db import models
from django.db.models import Exists, OuterRef

from apps.inspections.models import InspectionResult


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
            return self.filter(inspection__store__owner=user)
        return self.none()


class Ticket(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        CLOSED = "CLOSED", "Closed"

    inspection = models.OneToOneField(
        "inspections.Inspection",
        on_delete=models.CASCADE,
        related_name="ticket",
    )
    deadline = models.DateField()
    issued_at = models.DateTimeField(auto_now_add=True)

    objects = TicketManager()

    class Meta:
        ordering = ["-issued_at"]

    def __str__(self):
        return f"Ticket #{self.pk} — {self.inspection.store}"

    def violations(self):
        """The failed results on this ticket's inspection.

        Each row is annotated with ``is_resolved``: true once at least one
        evidence row against it has been accepted.
        """
        accepted = Evidence.objects.filter(
            result=OuterRef("pk"),
            review_status=Evidence.ReviewStatus.ACCEPTED,
        )
        return (
            self.inspection.results.filter(outcome=InspectionResult.Outcome.FAIL)
            .select_related("checklist_item")
            .annotate(is_resolved=Exists(accepted))
            .order_by("checklist_item__ordering", "checklist_item__code")
        )

    @property
    def status(self):
        """Derived, never stored (design-notes §4).

        CLOSED once every violation is resolved, OPEN otherwise.
        """
        if self.violations().filter(is_resolved=False).exists():
            return self.Status.OPEN
        return self.Status.CLOSED


class EvidenceManager(models.Manager):
    def visible_to(self, user):
        if not user.is_authenticated:
            return self.none()
        if user.role == "INSPECTOR":
            return self.all()
        if user.role == "OWNER":
            return self.filter(result__inspection__store__owner=user)
        return self.none()


class Evidence(models.Model):
    """A store owner's proof of a fix, attached to one failed result.

    Append-only (design-notes assumption 4): a re-submission is a new
    row. Only the review fields are written after creation.
    """

    class ReviewStatus(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"

    result = models.ForeignKey(
        "inspections.InspectionResult",
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
        return f"Evidence for {self.result} ({self.get_review_status_display()})"
