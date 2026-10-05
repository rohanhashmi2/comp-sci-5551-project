from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.inspections.models import (
    ChecklistItem,
    Inspection,
    InspectionResult,
)
from apps.stores.models import Store


@pytest.fixture
def inspector(db):
    return User.objects.create_user(
        email="inspector@example.com",
        password="pw-does-not-matter",
        role=User.Role.INSPECTOR,
    )


@pytest.fixture
def owner_a(db):
    return User.objects.create_user(
        email="owner.a@example.com",
        password="pw-does-not-matter",
        role=User.Role.OWNER,
    )


@pytest.fixture
def owner_b(db):
    return User.objects.create_user(
        email="owner.b@example.com",
        password="pw-does-not-matter",
        role=User.Role.OWNER,
    )


@pytest.fixture
def store_a(owner_a):
    return Store.objects.create(
        name="Corner Market", address="1 Main St", owner=owner_a
    )


@pytest.fixture
def store_b(owner_b):
    return Store.objects.create(
        name="Riverside Cafe", address="42 River Rd", owner=owner_b
    )


@pytest.mark.django_db
def test_inspection_str_includes_store_and_date(store_a):
    inspection = Inspection.objects.create(
        store=store_a,
        scheduled_for=timezone.now() + timedelta(days=3),
    )
    text = str(inspection)
    assert "Corner Market" in text
    # ISO date prefix YYYY-MM-DD is present regardless of locale/time
    assert inspection.scheduled_for.strftime("%Y-%m-%d") in text


@pytest.mark.django_db
def test_inspection_defaults_to_scheduled_status(store_a):
    inspection = Inspection.objects.create(
        store=store_a,
        scheduled_for=timezone.now() + timedelta(days=3),
    )
    assert inspection.status == Inspection.Status.SCHEDULED
    assert inspection.status == "SCHEDULED"


@pytest.mark.django_db
def test_inspection_visible_to_filters_by_role(
    inspector, owner_a, owner_b, store_a, store_b
):
    """Supporting coverage of the InspectionManager branches."""
    a_insp = Inspection.objects.create(
        store=store_a, scheduled_for=timezone.now() + timedelta(days=1)
    )
    b_insp = Inspection.objects.create(
        store=store_b, scheduled_for=timezone.now() + timedelta(days=2)
    )

    inspector_qs = Inspection.objects.visible_to(inspector)
    assert a_insp in inspector_qs
    assert b_insp in inspector_qs
    assert inspector_qs.count() == 2

    assert list(Inspection.objects.visible_to(owner_a)) == [a_insp]
    assert list(Inspection.objects.visible_to(owner_b)) == [b_insp]
    assert list(Inspection.objects.visible_to(AnonymousUser())) == []

    weird = User(email="weird@example.com", role="GHOST")
    weird.set_unusable_password()
    weird.is_active = True
    assert weird.is_authenticated is True
    assert weird.role not in ("INSPECTOR", "OWNER")
    assert list(Inspection.objects.visible_to(weird)) == []


@pytest.mark.django_db
def test_checklist_item_str_returns_code_and_title():
    item = ChecklistItem.objects.create(
        code="XX-01", title="A thing to check", description="…", ordering=1
    )
    text = str(item)
    assert "XX-01" in text
    assert "A thing to check" in text


@pytest.mark.django_db
def test_inspection_result_unique_per_item(store_a):
    inspection = Inspection.objects.create(
        store=store_a, scheduled_for=timezone.now() + timedelta(days=1)
    )
    item = ChecklistItem.objects.create(
        code="XX-01", title="Dup check", description="…", ordering=1
    )
    InspectionResult.objects.create(
        inspection=inspection,
        checklist_item=item,
        outcome=InspectionResult.Outcome.PASS,
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        InspectionResult.objects.create(
            inspection=inspection,
            checklist_item=item,
            outcome=InspectionResult.Outcome.FAIL,
        )


@pytest.mark.django_db
def test_inspection_result_visible_to_filters_by_role(
    inspector, owner_a, owner_b, store_a, store_b
):
    a_insp = Inspection.objects.create(
        store=store_a, scheduled_for=timezone.now() + timedelta(days=1)
    )
    b_insp = Inspection.objects.create(
        store=store_b, scheduled_for=timezone.now() + timedelta(days=2)
    )
    item = ChecklistItem.objects.create(
        code="XX-01", title="Just one", description="…", ordering=1
    )
    a_result = InspectionResult.objects.create(
        inspection=a_insp,
        checklist_item=item,
        outcome=InspectionResult.Outcome.PASS,
    )
    item2 = ChecklistItem.objects.create(
        code="XX-02", title="Another", description="…", ordering=2
    )
    b_result = InspectionResult.objects.create(
        inspection=b_insp,
        checklist_item=item2,
        outcome=InspectionResult.Outcome.FAIL,
    )

    assert set(InspectionResult.objects.visible_to(inspector)) == {
        a_result,
        b_result,
    }
    assert list(InspectionResult.objects.visible_to(owner_a)) == [a_result]
    assert list(InspectionResult.objects.visible_to(owner_b)) == [b_result]
    assert list(InspectionResult.objects.visible_to(AnonymousUser())) == []


@pytest.mark.django_db
def test_inspection_result_outcome_check_constraint(store_a):
    inspection = Inspection.objects.create(
        store=store_a, scheduled_for=timezone.now() + timedelta(days=1)
    )
    item = ChecklistItem.objects.create(
        code="XX-01", title="Check", description="…", ordering=1
    )
    result = InspectionResult(
        inspection=inspection, checklist_item=item, outcome="BOGUS"
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        result.save()
