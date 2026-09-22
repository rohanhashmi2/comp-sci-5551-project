from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        INSPECTOR = "INSPECTOR", "Inspector"
        OWNER = "OWNER", "Owner"

    role = models.CharField(max_length=16, choices=Role.choices)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["INSPECTOR", "OWNER"]),
                name="user_role_valid",
            ),
        ]
