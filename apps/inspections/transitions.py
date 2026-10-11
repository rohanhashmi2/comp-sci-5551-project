"""State-machine transitions for Inspection.

The function ``apply(inspection, event)`` mutates ``inspection.status``
in place according to the ``_TRANSITIONS`` table and raises
``InvalidTransition`` if the move is not allowed. It does not save —
the caller runs the save inside the same atomic block as any other
writes.

Stories that extend the table:
    - Story 7 adds ("IN_PROGRESS", "submit") → "COMPLETED".
    - Story 10 adds ("COMPLETED", "schedule_follow_up") →
      "RE_INSPECTION_SCHEDULED".
"""


class InvalidTransition(Exception):  # noqa: N818  (design-notes name)
    """Raised when an inspection cannot move from its current state."""


_TRANSITIONS = {
    ("SCHEDULED", "begin"): "IN_PROGRESS",
}


def apply(inspection, event):
    key = (inspection.status, event)
    try:
        inspection.status = _TRANSITIONS[key]
    except KeyError as exc:
        raise InvalidTransition(
            f"Cannot {event!r} from status {inspection.status!r}"
        ) from exc
