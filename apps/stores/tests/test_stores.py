import pytest
from django.urls import reverse

from apps.accounts.models import User
from apps.stores.models import Store

STORE_ADD_URL = reverse("stores:add")
STORE_LIST_URL = reverse("stores:list")


@pytest.fixture
def inspector(db):
    return User.objects.create_user(
        email="inspector@example.com",
        password="pw-does-not-matter",
        role=User.Role.INSPECTOR,
    )


@pytest.fixture
def another_inspector(db):
    return User.objects.create_user(
        email="inspector2@example.com",
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
def logged_in_inspector(client, inspector):
    client.force_login(inspector)
    return client


@pytest.fixture
def logged_in_owner(client, owner):
    client.force_login(owner)
    return client


@pytest.mark.django_db
def test_ac03_01_successful_store_creation(logged_in_inspector, owner):
    """
    AC 3.1 — Successful store creation

    Given an inspector is logged in and a registered store owner exists
    When the inspector submits the store form with a name, an address, and
      that owner selected
    Then the system creates the store with that owner and the store appears
      in the inspector's store list
    """
    response = logged_in_inspector.post(
        STORE_ADD_URL,
        data={
            "name": "Corner Market",
            "address": "1 Main St, Anytown",
            "owner": owner.pk,
        },
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain
    assert response.redirect_chain[-1][0] == STORE_LIST_URL
    assert Store.objects.count() == 1

    store = Store.objects.get()
    assert store.name == "Corner Market"
    assert store.owner_id == owner.pk

    assert store in response.context["stores"]
    assert b"Corner Market" in response.content


@pytest.mark.django_db
def test_ac03_02_name_empty_rejected(logged_in_inspector, owner):
    """
    AC 3.2 — Store creation rejected when a required field is empty

    Given an inspector is logged in
    When the inspector submits the store form with the name left empty
    Then the system does not create the store and displays an error message
      naming the missing field
    """
    response = logged_in_inspector.post(
        STORE_ADD_URL,
        data={"name": "", "address": "1 Main St", "owner": owner.pk},
    )

    assert response.status_code == 200
    assert Store.objects.count() == 0
    assert "name" in response.context["form"].errors


@pytest.mark.django_db
def test_ac03_03_owner_select_lists_only_owners(
    logged_in_inspector, inspector, another_inspector, owner
):
    """
    AC 3.3 — Only users with the owner role can be assigned as owners

    Given an inspector is logged in and another inspector account exists
    When the inspector opens the store form
    Then the owner selection lists only accounts with the store owner role
      and does not list any inspector account
    """
    response = logged_in_inspector.get(STORE_ADD_URL)

    assert response.status_code == 200
    owner_queryset = response.context["form"].fields["owner"].queryset
    assert owner in owner_queryset
    assert inspector not in owner_queryset
    assert another_inspector not in owner_queryset


@pytest.mark.django_db
def test_ac03_04_owner_cannot_access_add_store(logged_in_owner, owner):
    """
    AC 3.4 — A store owner cannot create a store

    Given a store owner is logged in
    When the store owner requests the add-store page
    Then the system denies access (redirects away from the add-store page)
      and no store is created, even if the owner attempts to POST a
      well-formed payload.
    """
    get_response = logged_in_owner.get(STORE_ADD_URL)
    assert get_response.status_code == 302
    assert get_response.url == reverse("home")
    assert Store.objects.count() == 0

    post_response = logged_in_owner.post(
        STORE_ADD_URL,
        data={
            "name": "Owner-made Store",
            "address": "1 Main St",
            "owner": owner.pk,
        },
    )
    assert post_response.status_code == 302
    assert post_response.url == reverse("home")
    assert Store.objects.count() == 0


@pytest.mark.django_db
def test_direct_post_with_inspector_owner_rejected(
    logged_in_inspector, another_inspector
):
    """
    Supporting test for AC 3.3.

    AC 3.3 verifies that the owner select on the form lists only
    owner-role users. This test proves the server-side defense: a
    hand-crafted POST that submits an inspector's PK as the owner is
    rejected without creating a Store, because the form's ``owner``
    field queryset is restricted to owner-role users.
    """
    response = logged_in_inspector.post(
        STORE_ADD_URL,
        data={
            "name": "Should Not Be Created",
            "address": "1 Main St",
            "owner": another_inspector.pk,
        },
    )

    assert response.status_code == 200
    assert Store.objects.count() == 0
    assert "owner" in response.context["form"].errors
