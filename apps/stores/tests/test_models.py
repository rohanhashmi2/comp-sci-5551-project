import pytest
from django.utils import timezone

from apps.accounts.models import User
from apps.stores.models import Store


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        email="owner@example.com",
        password="pw-does-not-matter",
        role=User.Role.OWNER,
    )


@pytest.mark.django_db
def test_store_str_returns_name(owner):
    store = Store.objects.create(name="Corner Market", address="1 Main St", owner=owner)
    assert str(store) == "Corner Market"


@pytest.mark.django_db
def test_store_created_at_auto_set(owner):
    before = timezone.now()
    store = Store.objects.create(name="Corner Market", address="1 Main St", owner=owner)
    after = timezone.now()
    assert store.created_at is not None
    assert before <= store.created_at <= after
