from datetime import timedelta

from django.utils import timezone

from apps.common.templatetags.deadlines import days_remaining


def test_days_remaining_future_date():
    deadline = timezone.localdate() + timedelta(days=15)
    assert days_remaining(deadline) == "15 DAYS REMAINING"


def test_days_remaining_tomorrow_is_singular():
    deadline = timezone.localdate() + timedelta(days=1)
    assert days_remaining(deadline) == "1 DAY REMAINING"


def test_days_remaining_today():
    assert days_remaining(timezone.localdate()) == "DUE TODAY"


def test_days_remaining_past_date():
    deadline = timezone.localdate() - timedelta(days=3)
    assert days_remaining(deadline) == "OVERDUE — 3 DAYS PAST"
