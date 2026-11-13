import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.inspections.models import ChecklistItem, Inspection, InspectionResult
from apps.stores.models import Store
from apps.tickets.models import Ticket


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Keep uploaded inspection photos inside the test directory."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        email="owner@example.com",
        password="test-password",
        role=User.Role.OWNER,
    )


@pytest.fixture
def another_owner(db):
    return User.objects.create_user(
        email="another-owner@example.com",
        password="test-password",
        role=User.Role.OWNER,
    )


@pytest.fixture
def logged_in_owner(client, owner):
    client.force_login(owner)
    return client


@pytest.fixture
def checklist_item(db):
    return ChecklistItem.objects.create(
        code="FIRE-001",
        title="Fire safety",
        description="Check fire safety equipment.",
    )


@pytest.fixture
def inspector(db):
    return User.objects.create_user(
        email="inspector@example.com",
        password="test-password",
        role=User.Role.INSPECTOR,
    )



def _make_image():
    """Create a valid PNG image for the InspectionResult."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")

    return SimpleUploadedFile(
        "inspection-photo.png",
        buffer.getvalue(),
        content_type="image/png",
    )


def _create_ticket(owner, checklist_item, inspector, title="Failed inspection item"):
    """Create a ticket belonging to a particular store owner."""
    store = Store.objects.create(
        name=f"Store belonging to {owner.email}",
        address="1 Main Street",
        owner=owner,
    )

    inspection = Inspection.objects.create(
        store=store,
        scheduled_for=timezone.now() - timedelta(days=1),
        status=Inspection.Status.COMPLETED,
    )

    result = InspectionResult.objects.create(
        inspection=inspection,
        checklist_item=checklist_item,
        outcome=InspectionResult.Outcome.FAIL,
        comment="The requirement was not met.",
        photo=_make_image(),
        deadline=timezone.localdate() + timedelta(days=14),
    )

    return Ticket.objects.create(
        inspection=inspection,
        inspection_result=result,
        store=store,
        created_by=inspector,
        title=title,
        description=result.comment,
    )

@pytest.mark.django_db
def test_ac10_01_owner_can_view_ticket_list(
    logged_in_owner,
    owner,
    checklist_item,
    inspector,
):
    """
    AC 10.1  Owner sees tickets issued against their store
Given a store owner is logged in and a ticket has been issued against their store
When the store owner opens the ticket list
Then that ticket is listed with its store name, issue date, deadline, and status

    """
    ticket = _create_ticket(
        owner,
        checklist_item,
        inspector,
        title="Fire extinguisher missing",
    )

    response = logged_in_owner.get(
        reverse("tickets:owner_ticket_list")
    )

    assert response.status_code == 200

    assert ticket in response.context["tickets"]

    assertContains = response.content.decode()

    assert "Fire extinguisher missing" in assertContains
    assert "Fire extinguisher missing" in assertContains
    assert "No open tickets." not in assertContains

@pytest.mark.django_db
def test_ac10_02_owner_cannot_see_other_owners_tickets(
    logged_in_owner,
    owner,
    another_owner,
    checklist_item,
    inspector,
):
    """
    AC 10.2 Ticket list excludes another owner's tickets
Given a store owner is logged in and a ticket has been issued against a store belonging to a different owner
When the store owner opens the ticket list
Then that ticket is not listed

    """
    own_ticket = _create_ticket(
        owner,
        checklist_item,
        inspector,
        title="My store violation",
    )

    another_ticket = _create_ticket(
        another_owner,
        checklist_item,
        inspector,
        title="Another owner's violation",
    )

    response = logged_in_owner.get(
        reverse("tickets:owner_ticket_list")
    )

    assert response.status_code == 200

    tickets = list(response.context["tickets"])

    assert own_ticket in tickets
    assert another_ticket not in tickets

    content = response.content.decode()

    assert "My store violation" in content
    assert "Another owner's violation" not in content


@pytest.mark.django_db
def test_ac10_03_owner_with_no_tickets_sees_empty_list(
    logged_in_owner,
    owner,
    checklist_item,
    inspector,
):
    """
    AC 10.3 Empty ticket list
Given a store owner is logged in with no tickets issued against their store
When the store owner opens the ticket list
Then the system displays a message stating no tickets have been issued

    """
    response = logged_in_owner.get(
        reverse("tickets:owner_ticket_list")
    )

    assert response.status_code == 200

    assert len(response.context["tickets"]) == 0

    assert "No open tickets." in response.content.decode()