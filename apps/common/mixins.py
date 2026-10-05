from django.contrib.auth.mixins import UserPassesTestMixin
from django.shortcuts import redirect


class InspectorRequiredMixin(UserPassesTestMixin):
    """Deny access to anyone whose role is not INSPECTOR.

    Role is compared against the literal string ``"INSPECTOR"`` to avoid
    importing from ``apps.accounts`` — ``apps.common`` is intentionally
    free of feature-app dependencies.
    """

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.role == "INSPECTOR"

    def handle_no_permission(self):
        if self.request.user.is_authenticated:
            # Authenticated non-inspector → home router sends them to
            # their correct dashboard. Matches Story 2's inline guard.
            return redirect("home")
        # Anonymous → fall through to LoginRequiredMixin's redirect to
        # LOGIN_URL with ?next=<path>.
        return super().handle_no_permission()
