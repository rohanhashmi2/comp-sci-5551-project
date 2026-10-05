import pytest
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.urls import path, reverse
from django.views.generic import View

from apps.accounts.models import User
from apps.common.mixins import InspectorRequiredMixin
from config.urls import urlpatterns as project_urlpatterns


class _ProbeView(LoginRequiredMixin, InspectorRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        return HttpResponse("ok")


# Extend the project URLconf with a probe-only route. Only resolves
# while the test module is active via @pytest.mark.urls.
urlpatterns = [
    *project_urlpatterns,
    path("__probe__/", _ProbeView.as_view(), name="probe"),
]


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


@pytest.mark.urls("apps.common.tests.test_mixins")
@pytest.mark.django_db
def test_inspector_required_mixin_allows_inspector(client, inspector):
    client.force_login(inspector)
    response = client.get(reverse("probe"))
    assert response.status_code == 200
    assert response.content == b"ok"


@pytest.mark.urls("apps.common.tests.test_mixins")
@pytest.mark.django_db
def test_inspector_required_mixin_redirects_owner_to_home(client, owner):
    client.force_login(owner)
    response = client.get(reverse("probe"))
    assert response.status_code == 302
    assert response.url == reverse("home")


@pytest.mark.urls("apps.common.tests.test_mixins")
@pytest.mark.django_db
def test_inspector_required_mixin_redirects_anonymous_to_login(client):
    response = client.get(reverse("probe"))
    assert response.status_code == 302
    # Falls through to LoginRequiredMixin → LOGIN_URL.
    assert response.url.startswith(reverse("accounts:login"))
