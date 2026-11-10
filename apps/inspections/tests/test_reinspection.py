"""Story 15 — Schedule a re-inspection."""

from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.inspections.models import Inspection, InspectionResult
from apps.stores.models import Store
from apps.tickets.models import Evidence, Ticket
from apps.tickets.tests.helpers import make_checklist_items, make_image, make_inspection

PASS = InspectionResult.Outcome.PASS
FAIL = InspectionResult.Outcome.FAIL
INSPECTOR_DASHBOARD_URL = reverse("accounts:inspector_dashboard")


def _reinspect_url(inspection):
    return reverse("inspections:reinspect", args=[inspection.pk])


def _future_datetime_string(days=7):
    return (timezone.now() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


def _past_datetime_string(days=1):
    return (timezone.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


def _messages(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


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
def store(owner):
    return Store.objects.create(name="Corner Market", address="1 Main St", owner=owner)


@pytest.fixture
def completed_with_open_ticket(store, inspector):
    """Completed inspection, one failed item, its ticket still OPEN with
    the owner's evidence rejected — the "evidence not sufficient" case."""
    items = make_checklist_items()
    inspection = make_inspection(
        store, items, [FAIL, PASS, PASS, PASS], inspector=inspector, days_ago=20
    )
    inspection.status = Inspection.Status.COMPLETED
    inspection.completed_at = timezone.now() - timedelta(days=19)
    inspection.save()
    Evidence.objects.create(
        ticket=inspection.tickets.get(),
        submitted_by=store.owner,
        photo=make_image("fix.png"),
        review_status=Evidence.ReviewStatus.REJECTED,
        reviewer_comment="The photo does not show the repaired seal.",
        reviewed_at=timezone.now(),
    )
    return inspection


@pytest.fixture
def logged_in_inspector(client, inspector):
    client.force_login(inspector)
    return client


@pytest.fixture
def logged_in_owner(client, owner):
    client.force_login(owner)
    return client


@pytest.mark.django_db
def test_ac15_01_successful_reinspection_scheduling(
    logged_in_inspector, completed_with_open_ticket
):
    """
    AC 15.1 — Successful re-inspection scheduling

    Given an inspector is logged in and a completed inspection still has
      an open ticket because the submitted evidence was not sufficient
    When the inspector schedules a re-inspection with a future date
    Then the system creates a new scheduled inspection of the same store
      linked to the original, the original's status becomes re-inspection
      scheduled, and the new visit appears on the inspector's dashboard
    """
    original = completed_with_open_ticket

    response = logged_in_inspector.post(
        _reinspect_url(original),
        data={"scheduled_for": _future_datetime_string(days=7)},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == INSPECTOR_DASHBOARD_URL
    original.refresh_from_db()
    assert original.status == Inspection.Status.RE_INSPECTION_SCHEDULED

    follow_up = Inspection.objects.get(previous_inspection=original)
    assert follow_up.store == original.store
    assert follow_up.status == Inspection.Status.SCHEDULED
    assert follow_up.scheduled_for > timezone.now()

    content = response.content.decode()
    assert "Re-inspection scheduled for Corner Market." in content
    assert reverse("inspections:conduct", args=[follow_up.pk]) in content
    assert "Re-inspection</span> of the" in content


@pytest.mark.django_db
def test_ac15_02_past_date_rejected(logged_in_inspector, completed_with_open_ticket):
    """
    AC 15.2 — Re-inspection rejected for a past date

    Given an inspector is logged in and a completed inspection has an
      open ticket
    When the inspector schedules a re-inspection with a date in the past
    Then the system does not create the re-inspection, the original stays
      completed, and an error states the date must be in the future
    """
    original = completed_with_open_ticket

    response = logged_in_inspector.post(
        _reinspect_url(original),
        data={"scheduled_for": _past_datetime_string(days=1)},
    )

    assert response.status_code == 200
    assert response.context["form"].has_error("scheduled_for", code="not_future")
    assert b"The date must be in the future." in response.content
    assert not Inspection.objects.filter(previous_inspection=original).exists()
    original.refresh_from_db()
    assert original.status == Inspection.Status.COMPLETED


@pytest.mark.django_db
def test_ac15_03_rejected_when_no_open_ticket(
    logged_in_inspector, completed_with_open_ticket
):
    """
    AC 15.3 — Re-inspection rejected when every ticket is resolved

    Given an inspector is logged in and every ticket of a completed
      inspection has been resolved by accepted evidence
    When the inspector schedules a re-inspection
    Then the system does not create the re-inspection and returns to the
      dashboard with a message stating no re-inspection is needed
    """
    original = completed_with_open_ticket
    original.tickets.update(status=Ticket.Status.RESOLVED)

    response = logged_in_inspector.post(
        _reinspect_url(original),
        data={"scheduled_for": _future_datetime_string()},
    )

    assert response.status_code == 302
    assert response.url == INSPECTOR_DASHBOARD_URL
    assert (
        "This inspection has no open tickets, so no re-inspection is needed."
        in _messages(response)
    )
    assert not Inspection.objects.filter(previous_inspection=original).exists()
    original.refresh_from_db()
    assert original.status == Inspection.Status.COMPLETED


@pytest.mark.django_db
def test_ac15_04_cannot_schedule_twice(logged_in_inspector, completed_with_open_ticket):
    """
    AC 15.4 — A re-inspection cannot be scheduled twice

    Given an inspector is logged in and a re-inspection has already been
      scheduled for an inspection
    When the inspector schedules another re-inspection for that inspection
    Then the system does not create a second re-inspection and returns to
      the dashboard with a message stating it cannot be scheduled in the
      inspection's current state
    """
    original = completed_with_open_ticket
    logged_in_inspector.post(
        _reinspect_url(original),
        data={"scheduled_for": _future_datetime_string(days=7)},
    )

    response = logged_in_inspector.post(
        _reinspect_url(original),
        data={"scheduled_for": _future_datetime_string(days=9)},
    )

    assert response.status_code == 302
    assert response.url == INSPECTOR_DASHBOARD_URL
    assert (
        "A re-inspection cannot be scheduled for this inspection in its "
        "current state." in _messages(response)
    )
    assert Inspection.objects.filter(previous_inspection=original).count() == 1


@pytest.mark.django_db
def test_ac15_05_owner_cannot_schedule_reinspection(
    logged_in_owner, completed_with_open_ticket
):
    """
    AC 15.5 — A store owner cannot schedule a re-inspection

    Given a store owner is logged in and their store has a completed
      inspection with an open ticket
    When the store owner opens and then submits the re-inspection form
    Then the system denies access and no re-inspection is created
    """
    original = completed_with_open_ticket
    url = _reinspect_url(original)

    get_response = logged_in_owner.get(url)
    post_response = logged_in_owner.post(
        url, data={"scheduled_for": _future_datetime_string()}
    )

    assert get_response.status_code == 302
    assert get_response.url == reverse("home")
    assert post_response.status_code == 302
    assert post_response.url == reverse("home")
    assert not Inspection.objects.filter(previous_inspection=original).exists()
    original.refresh_from_db()
    assert original.status == Inspection.Status.COMPLETED


# --- Supporting tests (not tied to a single AC) ---


@pytest.mark.django_db
def test_reinspection_rejected_for_in_progress_inspection(
    logged_in_inspector, store, inspector
):
    """An inspection that has not been submitted cannot be followed up."""
    in_progress = make_inspection(
        store, make_checklist_items(), [FAIL, PASS, PASS, PASS], inspector=inspector
    )

    response = logged_in_inspector.get(_reinspect_url(in_progress))

    assert response.status_code == 302
    assert response.url == INSPECTOR_DASHBOARD_URL
    assert not Inspection.objects.filter(previous_inspection=in_progress).exists()


@pytest.mark.django_db
def test_reinspection_form_lists_open_tickets(
    logged_in_inspector, completed_with_open_ticket
):
    """The form names the open tickets the follow-up visit is meant to verify."""
    ticket = completed_with_open_ticket.tickets.get()

    response = logged_in_inspector.get(_reinspect_url(completed_with_open_ticket))

    assert response.status_code == 200
    assert list(response.context["open_tickets"]) == [ticket]
    assert reverse("tickets:detail", args=[ticket.pk]).encode() in response.content


@pytest.mark.django_db
def test_dashboard_offers_reinspection_only_with_open_ticket(
    logged_in_inspector, completed_with_open_ticket
):
    """The dashboard button appears while a ticket is open and disappears
    once the ticket is resolved."""
    url = _reinspect_url(completed_with_open_ticket).encode()

    assert url in logged_in_inspector.get(INSPECTOR_DASHBOARD_URL).content

    completed_with_open_ticket.tickets.update(status=Ticket.Status.RESOLVED)
    assert url not in logged_in_inspector.get(INSPECTOR_DASHBOARD_URL).content


@pytest.mark.django_db
def test_ticket_detail_links_inspector_to_reinspection(
    logged_in_inspector, completed_with_open_ticket
):
    """After rejecting evidence, the inspector can schedule the visit from
    the ticket page."""
    ticket = completed_with_open_ticket.tickets.get()

    response = logged_in_inspector.get(reverse("tickets:detail", args=[ticket.pk]))

    assert _reinspect_url(completed_with_open_ticket).encode() in response.content
