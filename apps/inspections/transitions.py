"""State-machine transitions for Inspection.

The function ``apply(inspection, event)`` mutates ``inspection.status``
in place according to the ``_TRANSITIONS`` table and raises
``InvalidTransition`` if the move is not allowed. It does not save —
the caller runs the save inside the same atomic block as any other
writes.

The table today reflects the stories currently built:
    (SCHEDULED,   "begin")              → IN_PROGRESS              (Story 6)
    (IN_PROGRESS, "submit")             → COMPLETED                (Story 25)
    (COMPLETED,   "schedule_follow_up") → RE_INSPECTION_SCHEDULED  (Story 15)
"""


class InvalidTransition(Exception):  # noqa: N818  (design-notes name)
    """Raised when an inspection cannot move from its current state."""


_TRANSITIONS = {
    ("SCHEDULED", "begin"): "IN_PROGRESS",
    ("IN_PROGRESS", "submit"): "COMPLETED",
    ("COMPLETED", "schedule_follow_up"): "RE_INSPECTION_SCHEDULED",
}


def apply(inspection, event):
    key = (inspection.status, event)
    try:
        inspection.status = _TRANSITIONS[key]
    except KeyError as exc:
        raise InvalidTransition(
            f"Cannot {event!r} from status {inspection.status!r}"
        ) from exc
