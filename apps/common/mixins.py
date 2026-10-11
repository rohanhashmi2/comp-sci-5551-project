from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect


class RoleRequiredMixin(UserPassesTestMixin):
    """Deny access to anyone whose role is not ``required_role``.

    Role is compared against a string literal to avoid importing from
    ``apps.accounts`` — ``apps.common`` is intentionally free of
    feature-app dependencies.
    """

    required_role = None

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.role == self.required_role

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            # Authenticated user with the wrong role → home router sends
            # them to their correct dashboard. Matches Story 2's inline guard.
            return redirect("home")
        # Anonymous → fall through to LoginRequiredMixin's redirect to
        # LOGIN_URL with ?next=<path>.
        return super().handle_no_permission()


class InspectorRequiredMixin(RoleRequiredMixin):
    required_role = "INSPECTOR"


class OwnerRequiredMixin(RoleRequiredMixin):
    required_role = "OWNER"
