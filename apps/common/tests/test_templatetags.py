from datetime import timedelta

from django.utils import timezone

from apps.common.templatetags.deadlines import days_remaining, waiting_since


def test_days_remaining_future_deadline():
    deadline = timezone.now() + timedelta(days=15)
    assert days_remaining(deadline) == "15 DAYS REMAINING"


def test_days_remaining_tomorrow_is_singular():
    deadline = timezone.now() + timedelta(days=1)
    assert days_remaining(deadline) == "1 DAY REMAINING"


def test_days_remaining_today():
    assert days_remaining(timezone.now()) == "DUE TODAY"


def test_days_remaining_past_deadline():
    deadline = timezone.now() - timedelta(days=3)
    assert days_remaining(deadline) == "OVERDUE — 3 DAYS PAST"


def test_days_remaining_accepts_a_date():
    """After item 4, InspectionResult.deadline is a date, not a datetime.
    The filter must handle a pure date input."""
    deadline = timezone.localdate() + timedelta(days=5)
    assert days_remaining(deadline) == "5 DAYS REMAINING"


def test_waiting_since_fresh_submission_under_a_minute():
    """Django's timesince returns "0 minutes" for sub-minute ages; the
    filter must substitute a readable phrase."""
    submitted_at = timezone.now() - timedelta(seconds=30)
    assert waiting_since(submitted_at) == "less than a minute"


def test_waiting_since_at_least_one_minute_defers_to_timesince():
    submitted_at = timezone.now() - timedelta(minutes=5)
    out = waiting_since(submitted_at)
    # Avoid a Django-version-specific exact string; "minute" must appear
    # and the "less than a minute" short-circuit must not.
    assert "minute" in out
    assert out != "less than a minute"
