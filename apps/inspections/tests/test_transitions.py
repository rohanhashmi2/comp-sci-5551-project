import pytest

from apps.inspections import transitions
from apps.inspections.models import Inspection


def _unsaved(status):
    inspection = Inspection(status=status)
    return inspection


def test_transitions_scheduled_to_in_progress_via_begin():
    inspection = _unsaved(Inspection.Status.SCHEDULED)
    transitions.apply(inspection, "begin")
    assert inspection.status == Inspection.Status.IN_PROGRESS


def test_transitions_rejects_begin_from_in_progress():
    inspection = _unsaved(Inspection.Status.IN_PROGRESS)
    with pytest.raises(transitions.InvalidTransition):
        transitions.apply(inspection, "begin")


def test_transitions_rejects_unknown_event():
    inspection = _unsaved(Inspection.Status.SCHEDULED)
    with pytest.raises(transitions.InvalidTransition):
        transitions.apply(inspection, "teleport")
