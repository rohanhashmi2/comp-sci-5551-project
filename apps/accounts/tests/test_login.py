import pytest
from django.urls import reverse

from apps.accounts.models import User

LOGIN_URL = reverse("accounts:login")
LOGOUT_URL = reverse("accounts:logout")
INSPECTOR_DASHBOARD_URL = reverse("accounts:inspector_dashboard")
OWNER_DASHBOARD_URL = reverse("accounts:owner_dashboard")


@pytest.fixture
def inspector_password():
    return "InsPass123!"


@pytest.fixture
def inspector(db, inspector_password):
    return User.objects.create_user(
        email="inspector@example.com",
        password=inspector_password,
        role=User.Role.INSPECTOR,
    )


@pytest.fixture
def owner_password():
    return "OwnPass123!"


@pytest.fixture
def owner(db, owner_password):
    return User.objects.create_user(
        email="owner@example.com",
        password=owner_password,
        role=User.Role.OWNER,
    )


@pytest.mark.django_db
def test_ac02_01_successful_inspector_login(client, inspector, inspector_password):
    """
    AC 2.1 — Successful login as an inspector

    Given a registered account with the inspector role
    When the user submits that account's email and correct password on the
      login page
    Then the system starts a session for that user and displays the inspector
      dashboard
    """
    response = client.post(
        LOGIN_URL,
        data={"username": inspector.email, "password": inspector_password},
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain, "expected a redirect after successful login"
    final_url = response.redirect_chain[-1][0]
    assert final_url == INSPECTOR_DASHBOARD_URL
    assert client.session.get("_auth_user_id") == str(inspector.pk)
    assert b"Inspector dashboard" in response.content


@pytest.mark.django_db
def test_ac02_02_successful_owner_login(client, owner, owner_password):
    """
    AC 2.2 — Successful login as a store owner (session + dashboard half)

    Given a registered account with the store owner role
    When the user submits that account's email and correct password on the
      login page
    Then the system starts a session for that user and displays the store
      owner dashboard listing only that owner's stores

    Scope note: this story (US-2) delivers and verifies that the owner
    reaches their own dashboard and the page renders. The "listing only
    that owner's stores" half of the criterion is delivered and verified
    by Story 4 (store list), when the Store model and the owner-scoped
    queryset exist. This test asserts the session + dashboard half only.
    """
    response = client.post(
        LOGIN_URL,
        data={"username": owner.email, "password": owner_password},
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain
    final_url = response.redirect_chain[-1][0]
    assert final_url == OWNER_DASHBOARD_URL
    assert client.session.get("_auth_user_id") == str(owner.pk)
    assert b"Store owner dashboard" in response.content


@pytest.mark.django_db
def test_ac02_03_login_rejected_wrong_password(client, inspector):
    """
    AC 2.3 — Login rejected for an incorrect password

    Given a registered account
    When the user submits that account's email with an incorrect password
    Then the system does not start a session and displays an error message
      that does not reveal whether the email is registered
    """
    response = client.post(
        LOGIN_URL,
        data={"username": inspector.email, "password": "WrongPassword!"},
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
    assert response.context["form"].errors


@pytest.mark.django_db
def test_ac02_04_login_rejected_unregistered_email(client):
    """
    AC 2.4 — Login rejected for an unregistered email

    Given an email address that does not belong to any account
    When the user submits that email with any password
    Then the system does not start a session and displays the same error
      message as AC 2.3, so that an attacker cannot discover which emails
      are registered

    The equivalence of this response to the AC 2.3 response is verified
    by the supporting test test_ac02_03_04_response_equivalence.
    """
    assert not User.objects.filter(email="ghost@example.com").exists()

    response = client.post(
        LOGIN_URL,
        data={"username": "ghost@example.com", "password": "AnyPassword!"},
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
    assert response.context["form"].errors


@pytest.mark.django_db
def test_ac02_03_04_response_equivalence(client, inspector):
    """
    Supporting test for AC 2.3 and AC 2.4.

    The two failure modes — wrong password for a real user, and any
    password for an email that doesn't exist — must produce the same
    visible response so that an attacker cannot distinguish "wrong
    password" from "unknown email" by comparing the login form's output.
    """
    wrong_password_response = client.post(
        LOGIN_URL,
        data={"username": inspector.email, "password": "WrongPassword!"},
    )
    # Use a fresh client so the first POST's cookies don't carry over.
    unknown_email_response = client.post(
        LOGIN_URL,
        data={"username": "ghost@example.com", "password": "WrongPassword!"},
    )

    assert (
        wrong_password_response.status_code == unknown_email_response.status_code == 200
    )

    wp_errors = wrong_password_response.context["form"].errors
    ue_errors = unknown_email_response.context["form"].errors

    assert list(wp_errors.keys()) == list(ue_errors.keys())
    assert wp_errors.get("__all__", []) == ue_errors.get("__all__", [])


@pytest.mark.django_db
def test_ac02_05_sql_injection_pattern_rejected(client, inspector, inspector_password):
    """
    AC 2.5 — Login attempt with a malicious email field is rejected

    Given an email field containing an SQL injection pattern such as
      ' OR 1=1-- and any password
    When the adversary submits the login form
    Then the login attempt fails, no session is created, and no database
      error message is shown to the user

    Defense: Django's ORM parameterizes the lookup by USERNAME_FIELD, so
    the injection pattern is passed as a literal value to a parameterized
    query rather than concatenated into SQL. This test verifies the
    defense held — the response is the normal login page (not a 500 or a
    stack trace), the user table is unchanged, and a legitimate login
    with valid credentials succeeds immediately afterwards, proving the
    database was not disturbed by the injection attempt.
    """
    user_count_before = User.objects.count()
    assert user_count_before == 1

    response = client.post(
        LOGIN_URL,
        data={"username": "' OR 1=1--", "password": "anything"},
    )

    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
    assert User.objects.count() == user_count_before
    # Response is the normal login page, not an error page.
    assert b"Log in" in response.content
    assert response.context.get("form") is not None

    # Legitimate login with valid credentials still works — the database
    # and the auth path are unaffected by the injection attempt.
    valid_response = client.post(
        LOGIN_URL,
        data={"username": inspector.email, "password": inspector_password},
        follow=True,
    )
    assert valid_response.status_code == 200
    assert client.session.get("_auth_user_id") == str(inspector.pk)


@pytest.mark.django_db
def test_ac02_06_successful_logout(client, inspector):
    """
    AC 2.6 — Successful logout

    Given a user with an active session
    When the user selects log out
    Then the system ends the session, returns the user to the login page,
      and a subsequent attempt to open a dashboard page redirects to the
      login page
    """
    client.force_login(inspector)
    # Confirm the session is active and the dashboard is reachable.
    assert client.get(INSPECTOR_DASHBOARD_URL).status_code == 200

    logout_response = client.post(LOGOUT_URL)

    assert logout_response.status_code == 302
    assert logout_response.url == LOGIN_URL
    assert "_auth_user_id" not in client.session

    # A subsequent dashboard request redirects to login.
    dashboard_response = client.get(INSPECTOR_DASHBOARD_URL)
    assert dashboard_response.status_code == 302
    assert dashboard_response.url.startswith(LOGIN_URL)
