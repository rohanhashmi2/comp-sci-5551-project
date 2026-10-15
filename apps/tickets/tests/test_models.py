import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError

from apps.tickets.models import Evidence, Ticket

from .helpers import make_image


def _evidence(ticket, owner, status=Evidence.ReviewStatus.PENDING, comment=""):
    return Evidence.objects.create(
        ticket=ticket,
        submitted_by=owner,
        photo=make_image(),
        review_status=status,
        reviewer_comment=comment,
    )


@pytest.mark.django_db
def test_one_ticket_per_failed_result(inspection):
    """Every ticket points at a FAIL result on its inspection, one each."""
    tickets = list(inspection.tickets.order_by("pk"))
    assert [t.inspection_result.checklist_item.code for t in tickets] == [
        "TS-01",
        "TS-03",
    ]
    assert all(t.inspection_result.outcome == "FAIL" for t in tickets)
    assert all(t.status == Ticket.Status.OPEN for t in tickets)


@pytest.mark.django_db
def test_ticket_deadline_comes_from_result(ticket):
    assert ticket.deadline == ticket.inspection_result.deadline
    assert str(ticket) == f"Ticket #{ticket.pk} — Failed Inspection Item: TS-01"


@pytest.mark.django_db
def test_ticket_visible_to_filters_by_role(
    inspector, owner, other_owner, ticket, other_ticket
):
    owner_tickets = set(ticket.inspection.tickets.all())

    assert set(Ticket.objects.visible_to(inspector)) == owner_tickets | {other_ticket}
    assert set(Ticket.objects.visible_to(owner)) == owner_tickets
    assert list(Ticket.objects.visible_to(other_owner)) == [other_ticket]
    assert list(Ticket.objects.visible_to(AnonymousUser())) == []


@pytest.mark.django_db
def test_evidence_visible_to_filters_by_role(
    inspector, owner, other_owner, ticket, other_ticket
):
    mine = _evidence(ticket, owner)
    theirs = _evidence(other_ticket, other_owner)

    assert set(Evidence.objects.visible_to(inspector)) == {mine, theirs}
    assert list(Evidence.objects.visible_to(owner)) == [mine]
    assert list(Evidence.objects.visible_to(other_owner)) == [theirs]
    assert list(Evidence.objects.visible_to(AnonymousUser())) == []


@pytest.mark.django_db
def test_evidence_rejection_requires_comment_at_db_level(ticket, owner):
    """The DB rejects a REJECTED evidence row with an empty comment."""
    with pytest.raises(IntegrityError):
        _evidence(ticket, owner, Evidence.ReviewStatus.REJECTED, "")
