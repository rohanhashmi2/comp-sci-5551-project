"""Shared fixtures for the inspections test suite."""

import pytest
from django.core.management import call_command

from apps.inspections.models import ChecklistItem


@pytest.fixture
def checklist_items(db):
    """Load the 12-item ChecklistItem fixture.

    pytest-django's ``db`` fixture wraps each test in a transaction, so
    the loaded rows are rolled back after the test. Tests that need the
    catalogue opt in by taking this fixture as an argument.
    """
    call_command(
        "loaddata",
        "apps/inspections/fixtures/checklist_items.json",
        verbosity=0,
    )
    return list(
        ChecklistItem.objects.filter(is_active=True).order_by("ordering", "code")
    )
