import pytest
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

from apps.accounts.models import User
from apps.stores.models import Store

STORE_LIST_URL = reverse("stores:list")
OWNER_DASHBOARD_URL = reverse("accounts:owner_dashboard")


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
def logged_in_inspector(client, inspector):
    client.force_login(inspector)
    return client


@pytest.fixture
def logged_in_owner_a(client, owner_a):
    client.force_login(owner_a)
    return client


@pytest.mark.django_db
def test_ac04_01_inspector_sees_all_stores(logged_in_inspector, owner_a):
    """
    AC 4.1 — Inspector sees all stores

    Given an inspector is logged in and two stores exist
    When the inspector opens the store list
    Then both stores are listed with their name and address
    """
    store1 = Store.objects.create(
        name="Corner Market", address="1 Main St", owner=owner_a
    )
    store2 = Store.objects.create(
        name="Riverside Cafe", address="42 River Rd", owner=owner_a
    )

    response = logged_in_inspector.get(STORE_LIST_URL)

    assert response.status_code == 200
    stores_in_context = list(response.context["stores"])
    assert store1 in stores_in_context
    assert store2 in stores_in_context
    assert b"Corner Market" in response.content
    assert b"Riverside Cafe" in response.content
    assert b"1 Main St" in response.content
    assert b"42 River Rd" in response.content


@pytest.mark.django_db
def test_ac04_02_store_list_spans_all_owners(logged_in_inspector, owner_a, owner_b):
    """
    AC 4.2 — Store list spans all owners

    Given an inspector is logged in and one store exists owned by one store
      owner, and another store exists owned by a different store owner
    When the inspector opens the store list
    Then both stores are listed
    """
    store_a = Store.objects.create(
        name="Corner Market", address="1 Main St", owner=owner_a
    )
    store_b = Store.objects.create(
        name="Riverside Cafe", address="42 River Rd", owner=owner_b
    )

    response = logged_in_inspector.get(STORE_LIST_URL)

    assert response.status_code == 200
    stores_in_context = list(response.context["stores"])
    assert store_a in stores_in_context
    assert store_b in stores_in_context
    assert b"Corner Market" in response.content
    assert b"Riverside Cafe" in response.content


@pytest.mark.django_db
def test_ac04_03_empty_store_list(logged_in_inspector):
    """
    AC 4.3 — Empty store list

    Given an inspector is logged in with no stores assigned
    When the inspector opens the store list
    Then the system displays a message stating no stores are assigned and
      does not display an error
    """
    assert Store.objects.count() == 0

    response = logged_in_inspector.get(STORE_LIST_URL)

    assert response.status_code == 200
    assert list(response.context["stores"]) == []
    assert b"No stores yet" in response.content
    # Not an error page — the regular stores header renders.
    assert b"<h1>Stores</h1>" in response.content


@pytest.mark.django_db
def test_ac04_04_owner_sees_only_own_stores(logged_in_owner_a, owner_a, owner_b):
    """
    AC 4.4 — Store owner sees only their own stores

    Given a store owner is logged in with two stores assigned to them and
      another owner has a store
    When the store owner opens their dashboard
    Then both of their own stores are listed and the other owner's store
      does not appear
    """
    mine_1 = Store.objects.create(
        name="My Store One", address="1 First St", owner=owner_a
    )
    mine_2 = Store.objects.create(
        name="My Store Two", address="2 Second St", owner=owner_a
    )
    not_mine = Store.objects.create(
        name="Other Owner Store", address="99 Elsewhere", owner=owner_b
    )

    response = logged_in_owner_a.get(OWNER_DASHBOARD_URL)

    assert response.status_code == 200
    stores_in_context = list(response.context["stores"])
    assert mine_1 in stores_in_context
    assert mine_2 in stores_in_context
    assert not_mine not in stores_in_context
    assert b"My Store One" in response.content
    assert b"My Store Two" in response.content
    assert b"Other Owner Store" not in response.content


@pytest.mark.django_db
def test_store_visible_to_filters_by_role(inspector, owner_a, owner_b):
    """
    Supporting test for AC 4.1 – 4.4.

    Covers Store.objects.visible_to(user) directly, including the two
    branches the AC-mapped view tests don't exercise: an AnonymousUser
    and a user with a role string that is neither INSPECTOR nor OWNER.
    """
    a_store = Store.objects.create(name="A Store", address="A Address", owner=owner_a)
    b_store = Store.objects.create(name="B Store", address="B Address", owner=owner_b)

    inspector_qs = Store.objects.visible_to(inspector)
    assert a_store in inspector_qs
    assert b_store in inspector_qs
    assert inspector_qs.count() == 2

    owner_a_qs = Store.objects.visible_to(owner_a)
    assert list(owner_a_qs) == [a_store]

    owner_b_qs = Store.objects.visible_to(owner_b)
    assert list(owner_b_qs) == [b_store]

    anon_qs = Store.objects.visible_to(AnonymousUser())
    assert list(anon_qs) == []

    # Unknown role branch: a user whose role is neither INSPECTOR nor OWNER
    # must see nothing. Bypass create_user's defaults by writing the role
    # directly on the instance so the manager's fall-through branch is
    # exercised without touching the DB-level CheckConstraint.
    weird = User(email="weird@example.com", role="GHOST")
    weird.set_unusable_password()
    # Not saved — AnonymousUser-equivalent for the test, just typed.
    weird.is_active = True
    # Simulate "authenticated with unknown role"; we don't persist it
    # because the user_role_valid CheckConstraint would reject the row.
    assert weird.is_authenticated is True
    assert weird.role not in ("INSPECTOR", "OWNER")
    unknown_qs = Store.objects.visible_to(weird)
    assert list(unknown_qs) == []
