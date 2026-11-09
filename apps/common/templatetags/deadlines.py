from datetime import datetime

from django import template
from django.template.defaultfilters import timesince as default_timesince
from django.utils import timezone

register = template.Library()


@register.filter
def days_remaining(deadline):
    """Describe a deadline relative to today for ``.iq-deadline``.

    "15 DAYS REMAINING", "DUE TODAY", or "OVERDUE — 3 DAYS PAST".
    Counted in whole local calendar days. Uppercase, no period
    (design-notes §14.5). Accepts either a ``date`` or a ``datetime``;
    datetimes are projected to the local date first.
    """
    if isinstance(deadline, datetime):
        deadline_date = timezone.localdate(deadline)
    else:
        deadline_date = deadline
    delta = (deadline_date - timezone.localdate()).days
    if delta == 0:
        return "DUE TODAY"
    days = abs(delta)
    unit = "DAY" if days == 1 else "DAYS"
    if delta > 0:
        return f"{days} {unit} REMAINING"
    return f"OVERDUE — {days} {unit} PAST"


@register.filter
def waiting_since(submitted_at):
    """Human-readable "how long ago" for the review queue.

    Defers to Django's ``timesince`` for durations of at least a
    minute; for anything fresher returns "less than a minute" so a
    seconds-old submission does not render as "0 minutes".
    """
    delta = timezone.now() - submitted_at
    if delta.total_seconds() < 60:
        return "less than a minute"
    return default_timesince(submitted_at)
