"""Shared fixtures for the tickets test suite."""

import pytest

from apps.accounts.models import User
from apps.inspections.models import InspectionResult
from apps.stores.models import Store
from apps.tickets.models import Evidence

from .helpers import issue_ticket, make_checklist_items, make_image, make_inspection

PASS = InspectionResult.Outcome.PASS
FAIL = InspectionResult.Outcome.FAIL
NA = InspectionResult.Outcome.NOT_APPLICABLE


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
def ticket(owner, items):
    """A ticket on the owner's store: items 1 and 3 failed, 2 passed, 4 N/A."""
    store = Store.objects.create(name="Corner Market", address="1 Main St", owner=owner)
    return issue_ticket(make_inspection(store, items, [FAIL, PASS, FAIL, NA]))


@pytest.fixture
def other_ticket(other_owner, items):
    store = Store.objects.create(
        name="Riverside Cafe", address="42 River Rd", owner=other_owner
    )
    return issue_ticket(make_inspection(store, items, [FAIL, PASS, PASS, PASS]))


@pytest.fixture
def violation(ticket):
    return ticket.violations().first()


@pytest.fixture
def pending_evidence(violation, owner):
    return Evidence.objects.create(
        result=violation,
        submitted_by=owner,
        photo=make_image("fix.png"),
        note="Thermometer recalibrated.",
    )


@pytest.fixture
def logged_in_inspector(client, inspector):
    client.force_login(inspector)
    return client


@pytest.fixture
def logged_in_owner(client, owner):
    client.force_login(owner)
    return client
