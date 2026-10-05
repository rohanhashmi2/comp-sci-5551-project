from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.inspections.models import Inspection
from apps.stores.models import Store

SCHEDULE_URL = reverse("inspections:schedule")
INSPECTOR_DASHBOARD_URL = reverse("accounts:inspector_dashboard")


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
def logged_in_inspector(client, inspector):
    client.force_login(inspector)
    return client


@pytest.fixture
def logged_in_owner(client, owner):
    client.force_login(owner)
    return client


def _future_datetime_string(days=1):
    return (timezone.now() + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


def _past_datetime_string(days=1):
    return (timezone.now() - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M")


@pytest.mark.django_db
def test_ac05_01_successful_scheduling(logged_in_inspector, store):
    """
    AC 5.1 — Successful scheduling

    Given an inspector is logged in and a store exists
    When the inspector submits the schedule form with that store and a
      future date and time
    Then the system creates the inspection with status scheduled and the
      inspection appears on the inspector's dashboard
    """
    response = logged_in_inspector.post(
        SCHEDULE_URL,
        data={
            "store": store.pk,
            "scheduled_for": _future_datetime_string(days=7),
        },
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain
    assert response.redirect_chain[-1][0] == INSPECTOR_DASHBOARD_URL
    assert Inspection.objects.count() == 1

    inspection = Inspection.objects.get()
    assert inspection.store_id == store.pk
    assert inspection.status == Inspection.Status.SCHEDULED
    assert inspection in response.context["inspections"]


@pytest.mark.django_db
def test_ac05_02_past_date_rejected(logged_in_inspector, store):
    """
    AC 5.2 — Scheduling rejected for a past date

    Given an inspector is logged in and a store exists
    When the inspector submits the schedule form with a date and time in
      the past
    Then the system does not create the inspection and displays an error
      message stating the date must be in the future
    """
    response = logged_in_inspector.post(
        SCHEDULE_URL,
        data={
            "store": store.pk,
            "scheduled_for": _past_datetime_string(days=1),
        },
    )

    assert response.status_code == 200
    assert Inspection.objects.count() == 0
    assert "scheduled_for" in response.context["form"].errors
    errors = response.context["form"].errors.as_data()["scheduled_for"]
    assert errors[0].code == "not_future"


@pytest.mark.django_db
def test_ac05_03_empty_date_rejected(logged_in_inspector, store):
    """
    AC 5.3 — Scheduling rejected when no date is given

    Given an inspector is logged in and a store exists
    When the inspector submits the schedule form with the date left empty
    Then the system does not create the inspection and displays an error
      message naming the missing field
    """
    response = logged_in_inspector.post(
        SCHEDULE_URL,
        data={"store": store.pk, "scheduled_for": ""},
    )

    assert response.status_code == 200
    assert Inspection.objects.count() == 0
    assert "scheduled_for" in response.context["form"].errors


@pytest.mark.django_db
def test_ac05_04_owner_cannot_schedule(logged_in_owner, store):
    """
    AC 5.4 — A store owner cannot schedule an inspection

    Given a store owner is logged in
    When the store owner requests the schedule-inspection page
    Then the system denies access and no inspection is created
    """
    get_response = logged_in_owner.get(SCHEDULE_URL)
    assert get_response.status_code == 302
    assert get_response.url == reverse("home")
    assert Inspection.objects.count() == 0

    post_response = logged_in_owner.post(
        SCHEDULE_URL,
        data={
            "store": store.pk,
            "scheduled_for": _future_datetime_string(days=7),
        },
    )
    assert post_response.status_code == 302
    assert post_response.url == reverse("home")
    assert Inspection.objects.count() == 0
