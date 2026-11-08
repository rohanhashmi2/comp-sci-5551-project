from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.inspections.models import Inspection
from apps.stores.models import Store


def _submit_url(inspection):
    return reverse("inspections:submit", args=[inspection.pk])


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
def scheduled_inspection(store):
    return Inspection.objects.create(
        store=store,
        scheduled_for=timezone.now() + timedelta(days=1),
    )


@pytest.fixture
def in_progress_inspection(store):
    return Inspection.objects.create(
        store=store,
        scheduled_for=timezone.now() - timedelta(days=1),
        started_at=timezone.now() - timedelta(hours=1),
        status=Inspection.Status.IN_PROGRESS,
    )


@pytest.fixture
def completed_inspection(store):
    return Inspection.objects.create(
        store=store,
        scheduled_for=timezone.now() - timedelta(days=2),
        started_at=timezone.now() - timedelta(days=1),
        completed_at=timezone.now() - timedelta(hours=1),
        status=Inspection.Status.COMPLETED,
        notes="Original closing notes.",
    )


@pytest.fixture
def logged_in_inspector(client, inspector):
    client.force_login(inspector)
    return client


@pytest.fixture
def logged_in_owner(client, owner):
    client.force_login(owner)
    return client


@pytest.mark.django_db
def test_ac25_01_inspector_submits_in_progress_with_notes(
    logged_in_inspector, in_progress_inspection
):
    """
    AC 25.1 — Submit a completed inspection with closing notes

    Given an inspector is logged in and an inspection is in progress
    When the inspector submits the inspection with non-empty closing notes
    Then the system records the notes and the completion time, the status
      becomes completed, and the inspector returns to the dashboard
    """
    before = timezone.now()
    response = logged_in_inspector.post(
        _submit_url(in_progress_inspection),
        data={"notes": "All critical items corrected on site."},
        follow=True,
    )
    after = timezone.now()

    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == reverse("accounts:inspector_dashboard")

    in_progress_inspection.refresh_from_db()
    assert in_progress_inspection.status == Inspection.Status.COMPLETED
    assert in_progress_inspection.notes == "All critical items corrected on site."
    assert before <= in_progress_inspection.completed_at <= after


@pytest.mark.django_db
def test_ac25_02_submit_rejected_when_notes_empty(
    logged_in_inspector, in_progress_inspection
):
    """
    AC 25.2 — Submit rejected when closing notes are empty

    Given an inspector is logged in and an inspection is in progress
    When the inspector submits the inspection with the notes field empty
    Then the system does not submit the inspection and displays an error
      message stating closing notes are required
    """
    response = logged_in_inspector.post(
        _submit_url(in_progress_inspection),
        data={"notes": ""},
    )

    assert response.status_code == 200

    in_progress_inspection.refresh_from_db()
    assert in_progress_inspection.status == Inspection.Status.IN_PROGRESS
    assert in_progress_inspection.completed_at is None
    assert in_progress_inspection.notes == ""

    assert "notes" in response.context["form"].errors
    assert b"Closing notes are required" in response.content


@pytest.mark.django_db
def test_ac25_03_submit_rejected_from_scheduled(
    logged_in_inspector, scheduled_inspection
):
    """
    AC 25.3 — Submit rejected when the inspection has not been conducted

    Given an inspector is logged in and an inspection is still scheduled
      (its checklist has not been recorded)
    When the inspector submits the inspection
    Then the system does not change the inspection and returns to the
      dashboard with a message stating it cannot be submitted in its
      current state
    """
    response = logged_in_inspector.post(
        _submit_url(scheduled_inspection),
        data={"notes": "Attempted close."},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:inspector_dashboard")

    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.SCHEDULED
    assert scheduled_inspection.completed_at is None
    assert scheduled_inspection.notes == ""

    flashes = [str(m) for m in response.context["messages"]]
    assert any("cannot be submitted" in m.lower() for m in flashes)


@pytest.mark.django_db
def test_ac25_04_submit_rejected_when_already_completed(
    logged_in_inspector, completed_inspection
):
    """
    AC 25.4 — Submit rejected when the inspection is already submitted

    Given an inspector is logged in and an inspection has already been
      submitted
    When the inspector submits the inspection again
    Then the system does not change the inspection, the original closing
      notes and completion time are preserved, and the dashboard shows a
      message stating it has already been submitted
    """
    original_notes = completed_inspection.notes
    original_completed_at = completed_inspection.completed_at

    response = logged_in_inspector.post(
        _submit_url(completed_inspection),
        data={"notes": "Second submit attempt."},
        follow=True,
    )

    assert response.redirect_chain[-1][0] == reverse("accounts:inspector_dashboard")

    completed_inspection.refresh_from_db()
    assert completed_inspection.status == Inspection.Status.COMPLETED
    assert completed_inspection.notes == original_notes
    assert completed_inspection.completed_at == original_completed_at

    flashes = [str(m) for m in response.context["messages"]]
    assert any("already been submitted" in m.lower() for m in flashes)


@pytest.mark.django_db
def test_ac25_05_owner_cannot_submit(logged_in_owner, in_progress_inspection):
    """
    AC 25.5 — A store owner cannot submit an inspection

    Given a store owner is logged in
    When the store owner submits any inspection
    Then the system denies access and the inspection is unchanged
    """
    response = logged_in_owner.post(
        _submit_url(in_progress_inspection),
        data={"notes": "Owner attempt."},
    )

    assert response.status_code == 302
    assert response.url == reverse("home")

    in_progress_inspection.refresh_from_db()
    assert in_progress_inspection.status == Inspection.Status.IN_PROGRESS
    assert in_progress_inspection.completed_at is None
    assert in_progress_inspection.notes == ""


@pytest.mark.django_db
def test_submit_get_renders_form_for_in_progress(
    logged_in_inspector, in_progress_inspection
):
    """Supporting test: GET shows the notes form for an IN_PROGRESS inspection."""
    response = logged_in_inspector.get(_submit_url(in_progress_inspection))

    assert response.status_code == 200
    assert "form" in response.context
    assert b"Closing notes" in response.content
    assert b"Submit inspection" in response.content


@pytest.mark.django_db
def test_submit_get_redirects_from_completed(logged_in_inspector, completed_inspection):
    """Supporting test: GET on a COMPLETED inspection redirects with the
    already-submitted flash — mirrors the POST guard."""
    response = logged_in_inspector.get(_submit_url(completed_inspection), follow=True)

    assert response.redirect_chain[-1][0] == reverse("accounts:inspector_dashboard")
    flashes = [str(m) for m in response.context["messages"]]
    assert any("already been submitted" in m.lower() for m in flashes)


@pytest.mark.django_db
def test_submit_404_for_unknown_inspection(logged_in_inspector):
    """Supporting test: an inspector hitting an unknown pk gets 404."""
    response = logged_in_inspector.post(
        reverse("inspections:submit", args=[9999]),
        data={"notes": "No such row."},
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_dashboard_shows_submit_button_for_in_progress(
    logged_in_inspector, in_progress_inspection
):
    """Supporting test: the dashboard affordance for an IN_PROGRESS row is
    the Submit link — replaces the old 'Recorded' marker."""
    response = logged_in_inspector.get(reverse("accounts:inspector_dashboard"))

    content = response.content.decode()
    assert _submit_url(in_progress_inspection) in content
    assert "Submit" in content
    assert "Recorded" not in content


@pytest.mark.django_db
def test_dashboard_shows_completed_chip_for_completed(
    logged_in_inspector, completed_inspection
):
    """Supporting test: a COMPLETED row renders a quiet chip, not a button."""
    response = logged_in_inspector.get(reverse("accounts:inspector_dashboard"))

    content = response.content.decode()
    assert "Completed" in content
    assert _submit_url(completed_inspection) not in content
