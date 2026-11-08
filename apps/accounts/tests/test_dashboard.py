"""Owner dashboard tests. Supporting coverage; no AC maps to the dashboard."""

import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.inspections.models import InspectionResult
from apps.stores.models import Store
from apps.tickets.models import Ticket
from apps.tickets.tests.helpers import make_checklist_items, make_inspection

OWNER_DASHBOARD_URL = reverse("accounts:owner_dashboard")
FAIL = InspectionResult.Outcome.FAIL
PASS = InspectionResult.Outcome.PASS


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """FAIL-row photos land in a per-test tmp dir, not the project media/."""
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


@pytest.mark.django_db
def test_owner_dashboard_shows_per_store_open_ticket_count(
    client, inspector, owner, other_owner, items
):
    """Each store row on the owner dashboard shows its own open-ticket
    count, not the owner's project-wide total.

    Regression for a bug where the template looped stores but read a
    single ``tickets.count`` context key, so every row rendered the same
    number. Resolved tickets on the same store, and open tickets on
    other owners' stores, must not inflate the count.
    """
    # Owner has two stores. Bravo isn't bound to a variable because it's
    # only accessed through the view's response context, not directly.
    store_alpha = Store.objects.create(name="Alpha", address="1 A St", owner=owner)
    Store.objects.create(name="Bravo", address="2 B St", owner=owner)
    # A third store belongs to a different owner — must not leak into
    # Owner A's counts regardless of how many open tickets it has.
    other_store = Store.objects.create(
        name="Charlie", address="3 C St", owner=other_owner
    )

    # Alpha: two OPEN tickets from one inspection ...
    make_inspection(store_alpha, items, [FAIL, FAIL, PASS, PASS], inspector=inspector)
    # ... plus one ticket from a later inspection, marked RESOLVED — must
    # not count toward the "open" count on the dashboard.
    resolved = make_inspection(
        store_alpha, items, [FAIL, PASS, PASS, PASS], inspector=inspector
    )
    resolved.tickets.update(status=Ticket.Status.RESOLVED)

    # Bravo: no inspections, no tickets.

    # Charlie (other owner): three open tickets. If the dashboard leaks
    # across owners, these would surface.
    make_inspection(other_store, items, [FAIL, FAIL, FAIL, PASS], inspector=inspector)

    client.force_login(owner)
    response = client.get(OWNER_DASHBOARD_URL)

    assert response.status_code == 200

    stores_by_name = {s.name: s for s in response.context["stores"]}
    assert set(stores_by_name) == {"Alpha", "Bravo"}
    assert stores_by_name["Alpha"].open_ticket_count == 2
    assert stores_by_name["Bravo"].open_ticket_count == 0

    content = response.content.decode()
    # The button renders only on Alpha's row, carrying Alpha's own count.
    assert "View Open Tickets (2)" in content
    assert content.count("View Open Tickets") == 1
    # Bravo shows the empty-state line instead of the button.
    assert "No open tickets." in content
    # The pre-fix bug rendered the owner's project-wide total (2) on both
    # rows; the cross-owner total (3) must never appear.
    assert "View Open Tickets (3)" not in content
