"""Story 17 — Flag overdue tickets."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.inspections.models import InspectionResult
from apps.tickets.models import Ticket

OVERDUE_URL = reverse("tickets:overdue")
INSPECTOR_DASHBOARD_URL = reverse("accounts:inspector_dashboard")


def _set_deadline(ticket, days_from_today):
    InspectionResult.objects.filter(pk=ticket.inspection_result_id).update(
        deadline=timezone.localdate() + timedelta(days=days_from_today)
    )
    ticket.refresh_from_db()
    ticket.inspection_result.refresh_from_db()
    return ticket


@pytest.mark.django_db
def test_ac17_01_overdue_ticket_listed(logged_in_inspector, ticket):
    """
    AC 17.1 — An open ticket past its deadline is flagged

    Given an inspector is logged in and an open ticket's correction
      deadline has passed
    When the inspector opens the overdue tickets page
    Then that ticket is listed with its store, the failed item, the
      deadline, and how many days it is overdue
    """
    _set_deadline(ticket, -3)

    response = logged_in_inspector.get(OVERDUE_URL)

    assert response.status_code == 200
    assert list(response.context["tickets"]) == [ticket]
    content = response.content.decode()
    assert ticket.store.name in content
    assert ticket.inspection_result.checklist_item.code in content
    assert ticket.deadline.strftime("%Y-%m-%d") in content
    assert "OVERDUE — 3 DAYS PAST" in content
    assert reverse("tickets:detail", args=[ticket.pk]) in content


@pytest.mark.django_db
def test_ac17_02_ticket_within_deadline_not_listed(logged_in_inspector, inspection):
    """
    AC 17.2 — A ticket still within its deadline is not flagged

    Given an inspector is logged in, one open ticket is due today and
      another is due in the future
    When the inspector opens the overdue tickets page
    Then neither ticket is listed
    """
    due_today, due_later = inspection.tickets.order_by("pk")
    _set_deadline(due_today, 0)
    _set_deadline(due_later, 5)

    response = logged_in_inspector.get(OVERDUE_URL)

    assert list(response.context["tickets"]) == []


@pytest.mark.django_db
def test_ac17_03_resolved_ticket_not_listed(logged_in_inspector, ticket):
    """
    AC 17.3 — A resolved ticket is not flagged even after its deadline

    Given an inspector is logged in and a ticket whose deadline has passed
      was resolved by accepted evidence
    When the inspector opens the overdue tickets page
    Then that ticket is not listed
    """
    _set_deadline(ticket, -10)
    Ticket.objects.filter(pk=ticket.pk).update(status=Ticket.Status.RESOLVED)

    response = logged_in_inspector.get(OVERDUE_URL)

    assert ticket not in response.context["tickets"]


@pytest.mark.django_db
def test_ac17_04_dashboard_shows_overdue_count(
    logged_in_inspector, ticket, other_ticket
):
    """
    AC 17.4 — The inspector dashboard shows how many tickets are overdue

    Given an inspector is logged in and two open tickets at different
      stores have passed their deadlines
    When the inspector opens the dashboard
    Then the dashboard shows an overdue-tickets flag with the count 2 that
      links to the overdue tickets page
    """
    _set_deadline(ticket, -1)
    _set_deadline(other_ticket, -6)

    response = logged_in_inspector.get(INSPECTOR_DASHBOARD_URL)

    assert response.context["overdue_ticket_count"] == 2
    content = response.content.decode()
    assert "Overdue tickets (2)" in content
    assert OVERDUE_URL in content


@pytest.mark.django_db
def test_ac17_05_empty_overdue_list(logged_in_inspector, ticket):
    """
    AC 17.5 — No overdue tickets

    Given an inspector is logged in and no open ticket has passed its
      deadline
    When the inspector opens the overdue tickets page
    Then the system displays a message stating no tickets are overdue and
      the dashboard shows no overdue flag
    """
    response = logged_in_inspector.get(OVERDUE_URL)

    assert response.status_code == 200
    assert b"No tickets are overdue." in response.content
    assert b"iq-queue" not in response.content

    dashboard = logged_in_inspector.get(INSPECTOR_DASHBOARD_URL)
    assert b"Overdue tickets (" not in dashboard.content


@pytest.mark.django_db
def test_ac17_06_owner_cannot_open_overdue_list(logged_in_owner, ticket):
    """
    AC 17.6 — A store owner cannot open the overdue tickets page

    Given a store owner is logged in
    When the store owner requests the overdue tickets page
    Then the system denies access and redirects to the home page
    """
    _set_deadline(ticket, -2)

    response = logged_in_owner.get(OVERDUE_URL)

    assert response.status_code == 302
    assert response.url == reverse("home")


# --- Supporting tests (not tied to a single AC) ---


@pytest.mark.django_db
def test_overdue_list_orders_most_overdue_first(
    logged_in_inspector, ticket, other_ticket
):
    """The ticket that has been overdue longest is at the top."""
    _set_deadline(ticket, -1)
    _set_deadline(other_ticket, -8)

    response = logged_in_inspector.get(OVERDUE_URL)

    assert list(response.context["tickets"]) == [other_ticket, ticket]


@pytest.mark.django_db
def test_ticket_is_overdue_property(ticket):
    """is_overdue is true only for an OPEN ticket whose deadline is before today."""
    assert _set_deadline(ticket, 0).is_overdue is False
    assert _set_deadline(ticket, -1).is_overdue is True
    ticket.status = Ticket.Status.RESOLVED
    assert ticket.is_overdue is False


@pytest.mark.django_db
def test_owner_ticket_list_flags_overdue_ticket(logged_in_owner, inspection):
    """The owner sees an Overdue chip on the late ticket only."""
    late, on_time = inspection.tickets.order_by("pk")
    _set_deadline(late, -2)

    response = logged_in_owner.get(reverse("tickets:owner_ticket_list"))

    assert response.status_code == 200

    content = response.content.decode()
    assert content.count("· Overdue") == 1
    assert "OVERDUE — 2 DAYS PAST" in content
