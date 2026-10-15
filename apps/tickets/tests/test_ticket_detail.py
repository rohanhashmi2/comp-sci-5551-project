from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from django.utils.dateformat import format as date_format

from apps.inspections.models import Inspection, InspectionResult
from apps.stores.models import Store
from apps.tickets.models import Ticket

from .helpers import make_image


def _detail_url(ticket):
    return reverse("tickets:detail", args=[ticket.pk])


@pytest.mark.django_db
def test_ac11_01_ticket_detail_shows_violation(logged_in_owner, ticket):
    """
    AC 11.1 (rewritten) — Ticket detail shows the violation

    Given a store owner is logged in and a ticket has been issued against
      their store for a failed item
    When the store owner opens that ticket
    Then the failed checklist item is displayed with its comment and photo
      and the correction deadline is displayed

    See design-notes "Note: AC rewording in US-11" — Story 9 issues one
    ticket per failed item, so a ticket carries a single violation.
    """
    response = logged_in_owner.get(_detail_url(ticket))

    assert response.status_code == 200
    result = ticket.inspection_result
    content = response.content.decode()
    assert result.checklist_item.title in content
    assert result.comment in content
    assert result.photo.url in content
    local_deadline = timezone.localtime(result.deadline)
    assert date_format(local_deadline, "l, j F Y · H:i") in content


@pytest.mark.django_db
def test_ac11_02_passed_items_not_shown_as_violations(logged_in_owner, inspection):
    """
    AC 11.2 (rewritten) — Passed items are not shown as violations

    Given tickets have been issued from an inspection containing both
      passed and failed items
    When the store owner opens each ticket
    Then only failed items are shown as violations
    """
    tickets = list(inspection.tickets.all())
    assert len(tickets) == 2
    not_failed = inspection.results.exclude(outcome=InspectionResult.Outcome.FAIL)
    assert not_failed.count() == 2

    for ticket in tickets:
        response = logged_in_owner.get(_detail_url(ticket))
        assert response.status_code == 200
        assert response.context["result"].outcome == InspectionResult.Outcome.FAIL
        content = response.content.decode()
        for result in not_failed:
            assert result.checklist_item.title not in content


@pytest.mark.django_db
def test_ac11_03_owner_cannot_open_other_owners_ticket(
    logged_in_owner, ticket, other_ticket
):
    """
    AC 11.3 — Owner cannot open another owner's ticket

    Given a store owner is logged in and a ticket exists against a store
      belonging to a different owner
    When the store owner requests that ticket by its identifier
    Then the system responds with not found and no ticket details are
      displayed
    """
    response = logged_in_owner.get(_detail_url(other_ticket))

    assert response.status_code == 404
    assert b"Riverside Cafe" not in response.content
    assert other_ticket.description.encode() not in response.content


@pytest.mark.django_db
def test_inspector_can_open_any_ticket(logged_in_inspector, ticket, other_ticket):
    """Supporting test: inspectors have unscoped ticket visibility."""
    for t in (ticket, other_ticket):
        response = logged_in_inspector.get(_detail_url(t))
        assert response.status_code == 200
        assert response.context["ticket"] == t


@pytest.mark.django_db
def test_anonymous_ticket_detail_redirects_to_login(client, ticket):
    """Supporting test: the ticket page requires a session."""
    response = client.get(_detail_url(ticket))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


@pytest.mark.django_db
def test_open_ticket_shows_days_remaining(logged_in_owner, ticket):
    """Supporting test: the deadline block carries the days_remaining line."""
    response = logged_in_owner.get(_detail_url(ticket))

    assert ticket.status == Ticket.Status.OPEN
    assert b"14 DAYS REMAINING" in response.content


@pytest.mark.django_db
def test_ticket_list_links_to_ticket_detail(logged_in_owner, ticket):
    """Supporting test: Story 10's list leads to the Story 11 page."""
    response = logged_in_owner.get(reverse("tickets:owner_ticket_list"))

    assert _detail_url(ticket).encode() in response.content


@pytest.mark.django_db
def test_conducted_failure_opens_as_ticket_detail(client, inspector, owner, items):
    """Supporting test: a FAIL recorded through Story 9's conduct view
    produces a ticket the owner can open with its comment and deadline."""
    store = Store.objects.create(name="Corner Market", address="1 Main St", owner=owner)
    inspection = Inspection.objects.create(
        store=store, scheduled_for=timezone.now() + timedelta(days=1)
    )
    deadline = timezone.localtime(timezone.now() + timedelta(days=7))
    data = {
        "form-TOTAL_FORMS": str(len(items)),
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": str(len(items)),
    }
    for i in range(len(items)):
        data[f"form-{i}-id"] = ""
        data[f"form-{i}-outcome"] = "PASS"
    data["form-0-outcome"] = "FAIL"
    data["form-0-comment"] = "Walk-in cooler at 48°F."
    data["form-0-photo"] = make_image("cooler.png")
    data["form-0-deadline"] = deadline.strftime("%Y-%m-%dT%H:%M")

    client.force_login(inspector)
    client.post(reverse("inspections:conduct", args=[inspection.pk]), data=data)

    ticket = Ticket.objects.get()
    assert ticket.inspection_result.checklist_item == items[0]

    client.force_login(owner)
    response = client.get(_detail_url(ticket))

    assert response.status_code == 200
    assert "Walk-in cooler at 48°F." in response.content.decode()
    assert b"7 DAYS REMAINING" in response.content
