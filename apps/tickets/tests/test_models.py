import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError

from apps.tickets.models import Evidence, Ticket

from .helpers import make_image


def _evidence(result, owner, status=Evidence.ReviewStatus.PENDING, comment=""):
    return Evidence.objects.create(
        result=result,
        submitted_by=owner,
        photo=make_image(),
        review_status=status,
        reviewer_comment=comment,
    )


@pytest.mark.django_db
def test_ticket_status_closes_when_every_violation_accepted(ticket, owner):
    """Ticket.status is OPEN until every violation has accepted evidence."""
    first, second = ticket.violations()
    assert ticket.status == Ticket.Status.OPEN

    _evidence(first, owner, Evidence.ReviewStatus.ACCEPTED)
    assert ticket.status == Ticket.Status.OPEN

    _evidence(second, owner, Evidence.ReviewStatus.REJECTED, "Still dirty.")
    _evidence(second, owner)
    assert ticket.status == Ticket.Status.OPEN

    _evidence(second, owner, Evidence.ReviewStatus.ACCEPTED)
    assert ticket.status == Ticket.Status.CLOSED


@pytest.mark.django_db
def test_ticket_violations_lists_only_failed_results(ticket):
    violations = list(ticket.violations())
    assert [v.checklist_item.code for v in violations] == ["TS-01", "TS-03"]
    assert all(v.is_resolved is False for v in violations)


@pytest.mark.django_db
def test_ticket_visible_to_filters_by_role(
    inspector, owner, other_owner, ticket, other_ticket
):
    assert set(Ticket.objects.visible_to(inspector)) == {ticket, other_ticket}
    assert list(Ticket.objects.visible_to(owner)) == [ticket]
    assert list(Ticket.objects.visible_to(other_owner)) == [other_ticket]
    assert list(Ticket.objects.visible_to(AnonymousUser())) == []


@pytest.mark.django_db
def test_evidence_visible_to_filters_by_role(
    inspector, owner, other_owner, ticket, other_ticket
):
    mine = _evidence(ticket.violations().first(), owner)
    theirs = _evidence(other_ticket.violations().first(), other_owner)

    assert set(Evidence.objects.visible_to(inspector)) == {mine, theirs}
    assert list(Evidence.objects.visible_to(owner)) == [mine]
    assert list(Evidence.objects.visible_to(other_owner)) == [theirs]
    assert list(Evidence.objects.visible_to(AnonymousUser())) == []


@pytest.mark.django_db
def test_evidence_rejection_requires_comment_at_db_level(violation, owner):
    """The DB rejects a REJECTED evidence row with an empty comment."""
    with pytest.raises(IntegrityError):
        _evidence(violation, owner, Evidence.ReviewStatus.REJECTED, "")
