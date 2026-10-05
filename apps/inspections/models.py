from django.db import models


class InspectionManager(models.Manager):
    def visible_to(self, user):
        """Return the inspections a given user is permitted to see.

        Inspector  → every inspection.
        Owner      → inspections for stores this user owns.
        Anonymous / unknown role → no inspections.

        Mirrors ``StoreManager.visible_to`` — role compared as a string
        literal to avoid importing from ``apps.accounts.models``.
        """
        if not user.is_authenticated:
            return self.none()
        if user.role == "INSPECTOR":
            return self.all()
        if user.role == "OWNER":
            return self.filter(store__owner=user)
        return self.none()


class Inspection(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "SCHEDULED", "Scheduled"
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        RE_INSPECTION_SCHEDULED = "RE_INSPECTION_SCHEDULED", "Re-inspection scheduled"

    store = models.ForeignKey(
        "stores.Store",
        on_delete=models.PROTECT,
        related_name="inspections",
    )
    scheduled_for = models.DateTimeField()
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = InspectionManager()

    class Meta:
        ordering = ["scheduled_for"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "SCHEDULED",
                        "IN_PROGRESS",
                        "COMPLETED",
                        "RE_INSPECTION_SCHEDULED",
                    ]
                ),
                name="inspection_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.store} — {self.scheduled_for:%Y-%m-%d %H:%M}"
