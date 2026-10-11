import pytest
from django.urls import reverse
from django.utils.dateformat import format as date_format

from apps.inspections.models import InspectionResult


def _detail_url(ticket):
    return reverse("tickets:detail", args=[ticket.pk])


@pytest.mark.django_db
def test_ac11_01_ticket_detail_shows_all_violations(logged_in_owner, ticket):
    """
    AC 11.1 — Ticket detail shows all violations

    Given a store owner is logged in and a ticket has been issued against
      their store with two failed items
    When the store owner opens that ticket
    Then both failed checklist items are displayed with their comment and
      photo and the correction deadline is displayed
    """
    response = logged_in_owner.get(_detail_url(ticket))

    assert response.status_code == 200
    violations = response.context["violations"]
    assert len(violations) == 2
    content = response.content.decode()
    for violation in violations:
        assert violation.checklist_item.title in content
        assert violation.comment in content
        assert violation.photo.url in content
    assert date_format(ticket.deadline, "l, j F Y") in content


@pytest.mark.django_db
def test_ac11_02_passed_items_not_shown_as_violations(logged_in_owner, ticket):
    """
    AC 11.2 — Passed items are not shown as violations

    Given a ticket has been issued from an inspection containing both
      passed and failed items
    When the store owner opens that ticket
    Then only the failed items are listed as violations
    """
    response = logged_in_owner.get(_detail_url(ticket))

    assert response.status_code == 200
    violations = response.context["violations"]
    assert {v.outcome for v in violations} == {InspectionResult.Outcome.FAIL}
    content = response.content.decode()
    not_failed = ticket.inspection.results.exclude(
        outcome=InspectionResult.Outcome.FAIL
    )
    assert not_failed.count() == 2
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
    for violation in other_ticket.violations():
        assert violation.comment.encode() not in response.content


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

    assert response.context["status"] == "OPEN"
    assert b"14 DAYS REMAINING" in response.content
