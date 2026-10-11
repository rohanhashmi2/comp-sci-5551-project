from django import template
from django.utils import timezone

register = template.Library()


@register.filter
def days_remaining(deadline):
    """Describe a deadline relative to today for the ``.iq-deadline`` sub-line.

    "15 DAYS REMAINING", "DUE TODAY", or "OVERDUE — 3 DAYS PAST".
    Uppercase, no period (design-notes §14.5).
    """
    delta = (deadline - timezone.localdate()).days
    if delta == 0:
        return "DUE TODAY"
    days = abs(delta)
    unit = "DAY" if days == 1 else "DAYS"
    if delta > 0:
        return f"{days} {unit} REMAINING"
    return f"OVERDUE — {days} {unit} PAST"
