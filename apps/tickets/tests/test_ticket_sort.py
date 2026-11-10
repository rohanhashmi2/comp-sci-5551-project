"""Story 22 — Sort my tickets."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inspections.models import InspectionResult
from apps.tickets.models import Ticket

TICKET_LIST_URL = reverse("tickets:owner_ticket_list")


@pytest.fixture
def three_tickets(inspection, other_ticket):
    """Two of the owner's tickets plus one of another owner's.

    ``older`` was received 5 days ago and is due in 3 days; ``newer``
    was received 1 day ago and is due in 10 days, so the two sort orders
    disagree.
    """
    older, newer = inspection.tickets.order_by("pk")
    now = timezone.now()
    today = timezone.localdate()
    Ticket.objects.filter(pk=older.pk).update(created_at=now - timedelta(days=5))
    Ticket.objects.filter(pk=newer.pk).update(created_at=now - timedelta(days=1))
    InspectionResult.objects.filter(pk=older.inspection_result_id).update(
        deadline=today + timedelta(days=3)
    )
    InspectionResult.objects.filter(pk=newer.inspection_result_id).update(
        deadline=today + timedelta(days=10)
    )
    return older, newer, other_ticket


@pytest.mark.django_db
def test_ac22_01_sort_by_date_received(logged_in_owner, three_tickets):
    """
    AC 22.1 — Sort by date received

    Given a store owner is logged in and has two open tickets received on
      different dates
    When the store owner sorts the ticket list by date received
    Then the most recently received ticket is listed first
    """
    older, newer, _ = three_tickets

    response = logged_in_owner.get(TICKET_LIST_URL, {"sort": "received"})

    assert response.status_code == 200
    assert list(response.context["tickets"]) == [newer, older]


@pytest.mark.django_db
def test_ac22_02_sort_by_deadline(logged_in_owner, three_tickets):
    """
    AC 22.2 — Sort by deadline

    Given a store owner is logged in and has two open tickets with
      different correction deadlines
    When the store owner sorts the ticket list by deadline
    Then the ticket with the earliest deadline is listed first, and the
      deadline option is shown as the current sort
    """
    older, newer, _ = three_tickets

    response = logged_in_owner.get(TICKET_LIST_URL, {"sort": "deadline"})

    assert list(response.context["tickets"]) == [older, newer]
    assert b'<strong aria-current="true">Deadline</strong>' in response.content
    assert b'href="?sort=received"' in response.content


@pytest.mark.django_db
def test_ac22_03_default_sort_is_date_received(logged_in_owner, three_tickets):
    """
    AC 22.3 — Default order when no sort is chosen

    Given a store owner is logged in and has two open tickets
    When the store owner opens the ticket list without choosing a sort
    Then the tickets are listed newest received first and date received
      is shown as the current sort
    """
    older, newer, _ = three_tickets

    response = logged_in_owner.get(TICKET_LIST_URL)

    assert response.context["sort"] == "received"
    assert list(response.context["tickets"]) == [newer, older]
    assert b'<strong aria-current="true">Date received</strong>' in response.content
    assert b'href="?sort=deadline"' in response.content


@pytest.mark.django_db
def test_ac22_04_sorting_keeps_only_own_open_tickets(logged_in_owner, three_tickets):
    """
    AC 22.4 — Sorting does not change which tickets are shown

    Given a store owner is logged in, another owner has an open ticket,
      and one of this owner's tickets is resolved
    When the store owner sorts the ticket list by either option
    Then only this owner's open tickets are listed
    """
    older, newer, other_owners_ticket = three_tickets
    Ticket.objects.filter(pk=older.pk).update(status=Ticket.Status.RESOLVED)

    for sort in ("received", "deadline"):
        response = logged_in_owner.get(TICKET_LIST_URL, {"sort": sort})
        assert list(response.context["tickets"]) == [newer]
        assert other_owners_ticket.store.name.encode() not in response.content


# --- Supporting test (not tied to a single AC) ---


@pytest.mark.django_db
def test_deadline_ties_broken_by_newest_received(logged_in_owner, three_tickets):
    """Two tickets with the same deadline fall back to newest received first."""
    older, newer, _ = three_tickets
    InspectionResult.objects.filter(pk=older.inspection_result_id).update(
        deadline=timezone.localdate() + timedelta(days=10)
    )

    response = logged_in_owner.get(TICKET_LIST_URL, {"sort": "deadline"})

    assert list(response.context["tickets"]) == [newer, older]
