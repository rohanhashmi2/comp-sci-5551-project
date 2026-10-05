from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.inspections.models import ChecklistItem, Inspection, InspectionResult
from apps.stores.models import Store

INSPECTOR_DASHBOARD_URL = reverse("accounts:inspector_dashboard")


def _conduct_url(inspection):
    return reverse("inspections:conduct", args=[inspection.pk])


def _formset_post_data(outcomes):
    """Build the POST payload for the InspectionResult formset.

    ``outcomes`` is a list of outcome strings in checklist-item order.
    An empty string ``""`` simulates an unmarked radio.
    """
    data = {
        "form-TOTAL_FORMS": str(len(outcomes)),
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": str(len(outcomes)),
        "form-MAX_NUM_FORMS": str(len(outcomes)),
    }
    for i, outcome in enumerate(outcomes):
        data[f"form-{i}-id"] = ""
        data[f"form-{i}-outcome"] = outcome
    return data


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
def logged_in_inspector(client, inspector):
    client.force_login(inspector)
    return client


@pytest.fixture
def logged_in_owner(client, owner):
    client.force_login(owner)
    return client


@pytest.mark.django_db
def test_ac06_01_form_renders_every_active_item(
    logged_in_inspector, scheduled_inspection, checklist_items
):
    """
    AC 6.1 — Checklist renders every active item

    Given an inspector is logged in and an inspection is scheduled
    When the inspector opens the inspection form
    Then one row is displayed per active checklist item and each row
      offers pass, fail, and not applicable
    """
    response = logged_in_inspector.get(_conduct_url(scheduled_inspection))

    assert response.status_code == 200
    formset = response.context["formset"]
    assert len(formset.forms) == len(checklist_items)
    rendered_codes = [f.checklist_item_obj.code for f in formset.forms]
    assert rendered_codes == [item.code for item in checklist_items]
    first_form = formset.forms[0]
    choice_values = {value for value, _ in first_form.fields["outcome"].choices}
    assert choice_values == {"PASS", "FAIL", "NOT_APPLICABLE"}


@pytest.mark.django_db
def test_ac06_02_all_outcomes_recorded_and_status_in_progress(
    logged_in_inspector, scheduled_inspection, checklist_items
):
    """
    AC 6.2 — Recording outcomes for every item

    Given an inspector has the inspection form open
    When the inspector marks every checklist item as pass, fail, or not
      applicable and saves
    Then the system records one result for each checklist item and the
      inspection status becomes in progress
    """
    # Mix outcomes so this test also proves non-PASS values survive the save.
    cycle = ["PASS", "FAIL", "NOT_APPLICABLE"]
    outcomes = [cycle[i % 3] for i in range(len(checklist_items))]

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == INSPECTOR_DASHBOARD_URL

    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.IN_PROGRESS
    assert scheduled_inspection.started_at is not None
    assert scheduled_inspection.results.count() == len(checklist_items)

    saved = {
        r.checklist_item.code: r.outcome for r in scheduled_inspection.results.all()
    }
    expected = {item.code: outcomes[i] for i, item in enumerate(checklist_items)}
    assert saved == expected


@pytest.mark.django_db
def test_ac06_03_missing_outcome_rejected(
    logged_in_inspector, scheduled_inspection, checklist_items
):
    """
    AC 6.3 — Saving rejected when an item has no outcome

    Given an inspector has the inspection form open
    When the inspector saves with at least one checklist item left unmarked
    Then the system does not save the inspection and displays an error
      message identifying the unmarked items
    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[3] = ""  # Leave the fourth item unmarked.

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )

    assert response.status_code == 200
    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.SCHEDULED
    assert scheduled_inspection.started_at is None
    assert InspectionResult.objects.filter(inspection=scheduled_inspection).count() == 0
    formset = response.context["formset"]
    assert any(err.code == "incomplete" for err in formset.non_form_errors().as_data())
    # The unmarked row carries an inline error on the outcome field.
    unmarked_form = formset.forms[3]
    assert "outcome" in unmarked_form.errors


@pytest.mark.django_db
def test_ac06_04_pass_clean_distinguishable_from_unfilled(
    logged_in_inspector, scheduled_inspection, checklist_items
):
    """
    AC 6.4 — A passed inspection is distinguishable from an unfilled one

    Given an inspector has marked every checklist item as pass and saved
    When the inspection is retrieved
    Then a result exists for every checklist item with outcome pass and
      the inspection is not recorded as incomplete
    """
    # Before: unfilled state — SCHEDULED and zero results.
    assert scheduled_inspection.status == Inspection.Status.SCHEDULED
    assert scheduled_inspection.results.count() == 0

    outcomes = ["PASS"] * len(checklist_items)
    logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )

    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.IN_PROGRESS
    assert scheduled_inspection.results.count() == len(checklist_items)
    assert all(
        r.outcome == InspectionResult.Outcome.PASS
        for r in scheduled_inspection.results.all()
    )
    # The "distinguishable from incomplete" invariant: a passed-clean
    # inspection has one result per *active* checklist item.
    active_count = ChecklistItem.objects.filter(is_active=True).count()
    assert scheduled_inspection.results.count() == active_count


@pytest.mark.django_db
def test_ac06_05_owner_cannot_open_conduct_form(
    logged_in_owner, scheduled_inspection, checklist_items
):
    """
    AC 6.5 (rewritten) — A store owner cannot open the inspection form

    Given a store owner is logged in
    When the store owner requests the inspection form for any inspection
    Then the system denies access and no results are recorded

    See design-notes "Note: AC rewording in US-6" for why the original
    "assigned to a different inspector" wording was replaced.
    """
    outcomes = ["PASS"] * len(checklist_items)

    get_response = logged_in_owner.get(_conduct_url(scheduled_inspection))
    assert get_response.status_code == 302
    assert get_response.url == reverse("home")
    assert InspectionResult.objects.count() == 0

    post_response = logged_in_owner.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )
    assert post_response.status_code == 302
    assert post_response.url == reverse("home")
    assert InspectionResult.objects.count() == 0

    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.SCHEDULED
