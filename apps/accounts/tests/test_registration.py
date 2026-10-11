import pytest
from django.urls import reverse

from apps.accounts.models import User

REGISTER_URL = reverse("accounts:register")


@pytest.fixture
def valid_data():
    return {
        "email": "new.owner@example.com",
        "password1": "StrongPass123!",
        "password2": "StrongPass123!",
        "role": User.Role.OWNER,
    }


@pytest.mark.django_db
def test_ac01_01_successful_owner_registration(client, valid_data):
    """
    AC 1.1 — Successful registration as a store owner

    Given an email address that is not already registered
    When the user submits the registration form with that email, a valid
      password, the same password re-entered, and the store owner role selected
    Then the system creates the account with the store owner role and displays
      a message confirming the account is ready to use
    """
    response = client.post(REGISTER_URL, data=valid_data, follow=True)

    assert response.redirect_chain, "expected a redirect after successful post"
    assert User.objects.count() == 1
    user = User.objects.get()
    assert user.email == valid_data["email"]
    assert user.role == User.Role.OWNER
    assert any("ready" in str(m) for m in response.context["messages"])


@pytest.mark.django_db
def test_ac01_02_duplicate_email_rejected(client, valid_data):
    """
    AC 1.2 — Registration rejected for an email already in use

    Given an email address that already belongs to a registered account
    When the user submits the form with that email, a valid password, the same
      password re-entered, and a role selected
    Then the system does not create a second account and displays an error
      message stating the email is already registered
    """
    User.objects.create_user(
        email=valid_data["email"],
        password="SomeOtherStrongPass123!",
        role=User.Role.INSPECTOR,
    )
    assert User.objects.count() == 1

    response = client.post(REGISTER_URL, data=valid_data)

    assert response.status_code == 200
    assert User.objects.count() == 1
    assert "email" in response.context["form"].errors


@pytest.mark.django_db
def test_ac01_03_password_mismatch_rejected(client, valid_data):
    """
    AC 1.3 — Registration rejected when the passwords do not match

    Given an email address that is not already registered
    When the user submits the form with that email, a valid password, a
      different password in the confirmation field, and a role selected
    Then the system does not create the account and displays an error message
      stating the passwords do not match
    """
    valid_data["password2"] = "DifferentStrongPass456!"

    response = client.post(REGISTER_URL, data=valid_data)

    assert response.status_code == 200
    assert User.objects.count() == 0
    assert "password2" in response.context["form"].errors


@pytest.mark.django_db
def test_ac01_04_weak_password_rejected(client, valid_data):
    """
    AC 1.4 — Registration rejected for a password that fails the strength rules

    Given an email address that is not already registered
    When the user submits the form with that email, a password shorter than the
      minimum length, the same password re-entered, and a role selected
    Then the system does not create the account and displays an error message
      describing the password requirements
    """
    valid_data["password1"] = "abc"
    valid_data["password2"] = "abc"

    response = client.post(REGISTER_URL, data=valid_data)

    assert response.status_code == 200
    assert User.objects.count() == 0
    assert "password2" in response.context["form"].errors


@pytest.mark.django_db
def test_ac01_05_role_required(client, valid_data):
    """
    AC 1.5 — Registration rejected when no role is chosen

    Given an email address that is not already registered
    When the user submits the form with that email, a valid password, the same
      password re-entered, and no role selected
    Then the system does not create the account and displays an error message
      stating a role must be chosen
    """
    valid_data["role"] = ""

    response = client.post(REGISTER_URL, data=valid_data)

    assert response.status_code == 200
    assert User.objects.count() == 0
    assert "role" in response.context["form"].errors
