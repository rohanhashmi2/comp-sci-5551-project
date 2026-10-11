import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.inspections.models import Inspection, InspectionResult
from apps.stores.models import Store
from apps.tickets.models import Evidence
from apps.tickets.tests.helpers import (
    issue_ticket,
    make_checklist_items,
    make_image,
    make_inspection,
)

PASS = InspectionResult.Outcome.PASS
FAIL = InspectionResult.Outcome.FAIL


def _history_url(store):
    return reverse("stores:history", args=[store.pk])


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def inspector(db):
    return User.objects.create_user(
        email="inspector@example.com",
        password="pw-does-not-matter",
        role=User.Role.INSPECTOR,
    )


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        email="owner@example.com",
        password="pw-does-not-matter",
        role=User.Role.OWNER,
    )


@pytest.fixture
def other_owner(db):
    return User.objects.create_user(
        email="other.owner@example.com",
        password="pw-does-not-matter",
        role=User.Role.OWNER,
    )


@pytest.fixture
def items(db):
    return make_checklist_items()


@pytest.fixture
def store(owner):
    return Store.objects.create(name="Corner Market", address="1 Main St", owner=owner)


@pytest.fixture
def other_store(other_owner):
    return Store.objects.create(
        name="Riverside Cafe", address="42 River Rd", owner=other_owner
    )


@pytest.mark.django_db
def test_ac14_01_inspector_views_history_of_any_store(client, inspector, store, items):
    """
    AC 14.1 — Inspector views the history of any store

    Given an inspector is logged in and a store has two completed
      inspections
    When the inspector opens that store's history
    Then both inspections are listed in date order with their outcome and
      ticket status
    """
    # Created newest-first so the assertion proves the view sorts by date.
    recent = make_inspection(store, items, [PASS, PASS, PASS, PASS], days_ago=3)
    older = make_inspection(store, items, [FAIL, PASS, FAIL, PASS], days_ago=40)
    ticket = issue_ticket(older)
    client.force_login(inspector)

    response = client.get(_history_url(store))

    assert response.status_code == 200
    listed = list(response.context["inspections"])
    assert listed == [older, recent]
    assert [i.violation_count for i in listed] == [2, 0]
    content = response.content.decode()
    assert "✕ 2 violations" in content
    assert "✓ Passed" in content
    assert reverse("tickets:detail", args=[ticket.pk]) in content
    assert ">Open</span>" in content
    assert "No ticket" in content


@pytest.mark.django_db
def test_ac14_02_owner_views_history_of_own_store(client, owner, store, items):
    """
    AC 14.2 — Owner views the history of their own store

    Given a store owner is logged in and their store has a completed
      inspection
    When the store owner opens their store's history
    Then that inspection is listed with its outcome and ticket status
    """
    inspection = make_inspection(store, items, [FAIL, PASS, PASS, PASS])
    issue_ticket(inspection)
    client.force_login(owner)

    response = client.get(_history_url(store))

    assert response.status_code == 200
    assert list(response.context["inspections"]) == [inspection]
    content = response.content.decode()
    assert "✕ 1 violation<" in content
    assert ">Open</span>" in content


@pytest.mark.django_db
def test_ac14_03_owner_cannot_view_other_stores_history(
    client, owner, other_store, items
):
    """
    AC 14.3 — Owner cannot view another store's history

    Given a store owner is logged in and a completed inspection exists for
      a store belonging to a different owner
    When the store owner requests that store's history by its identifier
    Then the system responds with not found and no inspection records are
      displayed
    """
    make_inspection(other_store, items, [FAIL, PASS, PASS, PASS])
    client.force_login(owner)

    response = client.get(_history_url(other_store))

    assert response.status_code == 404
    assert b"Riverside Cafe" not in response.content
    assert b"violation" not in response.content


@pytest.mark.django_db
def test_ac14_04_empty_history(client, inspector, store):
    """
    AC 14.4 — Empty history

    Given an inspector is logged in and a store has no completed
      inspections
    When the inspector opens that store's history
    Then the system displays a message stating no inspections have been
      recorded
    """
    # A scheduled visit is not part of the history.
    Inspection.objects.create(store=store, scheduled_for="2030-01-01T09:00Z")
    client.force_login(inspector)

    response = client.get(_history_url(store))

    assert response.status_code == 200
    assert list(response.context["inspections"]) == []
    assert b"No inspections have been recorded." in response.content


@pytest.mark.django_db
def test_closed_ticket_shown_as_closed_in_history(client, owner, store, items):
    """Supporting test: the history's ticket status follows evidence review."""
    ticket = issue_ticket(make_inspection(store, items, [FAIL, PASS, PASS, PASS]))
    Evidence.objects.create(
        result=ticket.violations().get(),
        submitted_by=owner,
        photo=make_image(),
        review_status=Evidence.ReviewStatus.ACCEPTED,
    )
    client.force_login(owner)

    response = client.get(_history_url(store))

    assert ">Closed</span>" in response.content.decode()


@pytest.mark.django_db
def test_history_links_from_store_list_and_owner_dashboard(
    client, inspector, owner, store
):
    """Supporting test: both roles can reach the history page."""
    client.force_login(inspector)
    assert _history_url(store).encode() in client.get(reverse("stores:list")).content

    client.force_login(owner)
    dashboard = client.get(reverse("accounts:owner_dashboard"))
    assert _history_url(store).encode() in dashboard.content
