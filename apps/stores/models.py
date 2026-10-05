from django.conf import settings
from django.db import models


class StoreManager(models.Manager):
    def visible_to(self, user):
        """Return the stores a given user is permitted to see.

        Inspector  → every store.
        Owner      → stores where this user is the owner.
        Anonymous / unknown role → no stores.

        Role is compared as a string literal to avoid importing from
        ``apps.accounts.models`` — matches the ``InspectorRequiredMixin``
        pattern in ``apps.common.mixins``.
        """
        if not user.is_authenticated:
            return self.none()
        if user.role == "INSPECTOR":
            return self.all()
        if user.role == "OWNER":
            return self.filter(owner=user)
        return self.none()


class Store(models.Model):
    name = models.CharField(max_length=200)
    address = models.TextField()
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        limit_choices_to={"role": "OWNER"},
        related_name="stores",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    objects = StoreManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
