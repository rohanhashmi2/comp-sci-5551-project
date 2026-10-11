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
    started_at = models.DateTimeField(null=True, blank=True)
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


class ChecklistItem(models.Model):
    code = models.CharField(max_length=16, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    is_active = models.BooleanField(default=True)
    ordering = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordering", "code"]

    def __str__(self):
        return f"{self.code} — {self.title}"


class InspectionResultManager(models.Manager):
    def visible_to(self, user):
        if not user.is_authenticated:
            return self.none()
        if user.role == "INSPECTOR":
            return self.all()
        if user.role == "OWNER":
            return self.filter(inspection__store__owner=user)
        return self.none()


class InspectionResult(models.Model):
    class Outcome(models.TextChoices):
        PASS = "PASS", "Pass"
        FAIL = "FAIL", "Fail"
        NOT_APPLICABLE = "NOT_APPLICABLE", "Not applicable"

    inspection = models.ForeignKey(
        Inspection,
        on_delete=models.CASCADE,
        related_name="results",
    )
    checklist_item = models.ForeignKey(
        ChecklistItem,
        on_delete=models.PROTECT,
        related_name="+",
    )
    outcome = models.CharField(max_length=16, choices=Outcome.choices)
    # comment and photo ship with the schema now (blank/null) so Dev 2's
    # Stories 7 and 8 only need to extend the form + add clean() checks,
    # not a new migration per story.
    comment = models.TextField(blank=True)
    photo = models.ImageField(null=True, blank=True, upload_to="results/%Y/%m/")
    created_at = models.DateTimeField(auto_now_add=True)

    objects = InspectionResultManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["inspection", "checklist_item"],
                name="one_result_per_item_per_inspection",
            ),
            models.CheckConstraint(
                condition=models.Q(outcome__in=["PASS", "FAIL", "NOT_APPLICABLE"]),
                name="result_outcome_valid",
            ),
        ]

    def __str__(self):
        return f"{self.checklist_item.code}: {self.get_outcome_display()}"
