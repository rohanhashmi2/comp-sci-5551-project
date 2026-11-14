from datetime import timedelta
import pytest
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localtime

from apps.inspections.models import ChecklistItem, Inspection, InspectionResult
from apps.stores.models import Store
from apps.tickets.models import Ticket

from .helpers import make_image

@pytest.fixture
def checklist_item(db):
    return ChecklistItem.objects.create(
        code="FIRE-001",
        title="Fire safety",
        description="Check fire safety equipment.",
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
        photo=make_image(),
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

    content = response.content.decode()

    assert ticket.title in content
    assert ticket.store.name in content
    assert localtime(ticket.created_at).strftime("%Y-%m-%d") in content
    assert ticket.inspection_result.deadline.strftime("%Y-%m-%d") in content
    assert ticket.get_status_display() in content
    assert "No open tickets." not in content

@pytest.mark.django_db
def test_ac10_02_owner_cannot_see_other_owners_tickets(
    logged_in_owner,
    owner,
    other_owner,
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
        other_owner,
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
    assert b"iq-empty" in response.content