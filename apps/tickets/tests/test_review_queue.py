from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.tickets.models import Evidence

from .helpers import make_image

REVIEW_QUEUE_URL = reverse("tickets:review_queue")


def _accepted(ticket, owner):
    return Evidence.objects.create(
        ticket=ticket,
        submitted_by=owner,
        photo=make_image("accepted.png"),
        review_status=Evidence.ReviewStatus.ACCEPTED,
        reviewed_at=timezone.now(),
    )


def _rejected(ticket, owner):
    return Evidence.objects.create(
        ticket=ticket,
        submitted_by=owner,
        photo=make_image("rejected.png"),
        review_status=Evidence.ReviewStatus.REJECTED,
        reviewer_comment="Photo did not show the thermometer reading.",
        reviewed_at=timezone.now(),
    )


@pytest.mark.django_db
def test_ac26_01_pending_evidence_appears_in_queue(
    logged_in_inspector, ticket, pending_evidence
):
    """
    AC 26.1 — Pending evidence appears in the queue

    Given an inspector is logged in and evidence has been submitted
      against a violation and awaits review
    When the inspector opens the review queue
    Then that evidence is listed with its store, its submitted time, and
      the violation it addresses, and the row links to the ticket's
      review form
    """
    response = logged_in_inspector.get(REVIEW_QUEUE_URL)

    assert response.status_code == 200
    assert list(response.context["evidence_list"]) == [pending_evidence]

    content = response.content.decode()
    store = ticket.store
    item = ticket.inspection_result.checklist_item
    submitted_local = timezone.localtime(pending_evidence.submitted_at)

    assert store.name in content
    assert submitted_local.strftime("%Y-%m-%d %H:%M") in content
    assert item.code in content
    assert item.title in content

    review_href = f"{reverse('tickets:detail', args=[ticket.pk])}#evidence"
    assert review_href in content


@pytest.mark.django_db
def test_ac26_02_reviewed_evidence_is_not_in_queue(logged_in_inspector, ticket, owner):
    """
    AC 26.2 — Reviewed evidence is not in the queue

    Given an inspector is logged in and evidence has already been
      reviewed as either accepted or rejected
    When the inspector opens the review queue
    Then that evidence is not listed
    """
    accepted = _accepted(ticket, owner)
    rejected = _rejected(ticket, owner)

    response = logged_in_inspector.get(REVIEW_QUEUE_URL)

    assert response.status_code == 200
    queue = list(response.context["evidence_list"])
    assert accepted not in queue
    assert rejected not in queue
    assert queue == []


@pytest.mark.django_db
def test_ac26_03_queue_oldest_pending_first(logged_in_inspector, ticket, owner):
    """
    AC 26.3 — Queue shows the oldest pending submission first

    Given an inspector is logged in and two pieces of evidence are
      pending, one submitted earlier than the other
    When the inspector opens the review queue
    Then the earlier submission appears above the later one

    Insertion order deliberately disagrees with chronological order:
    the newer row is inserted first (lower pk), the older row is
    inserted second (higher pk). A queryset that falls back to
    insertion/pk order would yield [newer, older]; passing this test
    requires the queryset to order by submitted_at explicitly.
    """
    newer = Evidence.objects.create(
        ticket=ticket, submitted_by=owner, photo=make_image("newer.png")
    )
    older = Evidence.objects.create(
        ticket=ticket, submitted_by=owner, photo=make_image("older.png")
    )
    # auto_now_add blocks direct assignment on create; update() bypasses it.
    Evidence.objects.filter(pk=newer.pk).update(
        submitted_at=timezone.now() - timedelta(minutes=5)
    )
    Evidence.objects.filter(pk=older.pk).update(
        submitted_at=timezone.now() - timedelta(days=3)
    )

    response = logged_in_inspector.get(REVIEW_QUEUE_URL)

    assert response.status_code == 200
    queue = list(response.context["evidence_list"])
    assert [e.pk for e in queue] == [older.pk, newer.pk]


@pytest.mark.django_db
def test_ac26_04_empty_queue(logged_in_inspector):
    """
    AC 26.4 — Empty queue

    Given an inspector is logged in and no evidence is pending
    When the inspector opens the review queue
    Then the system displays a message stating no evidence is awaiting
      review and does not show a queue list
    """
    response = logged_in_inspector.get(REVIEW_QUEUE_URL)

    assert response.status_code == 200
    assert list(response.context["evidence_list"]) == []
    # Structural check — no assertion on English copy. The empty-state
    # block renders and the queue list does not.
    assert b"iq-empty" in response.content
    assert b'class="iq-queue"' not in response.content


@pytest.mark.django_db
def test_ac26_05_owner_cannot_open_queue(logged_in_owner, pending_evidence):
    """
    AC 26.5 — A store owner cannot open the review queue

    Given a store owner is logged in
    When the store owner requests the review queue
    Then the system denies access and no evidence is listed
    """
    response = logged_in_owner.get(REVIEW_QUEUE_URL)

    assert response.status_code == 302
    assert response.url == reverse("home")

    # The pending row still exists — the owner was blocked before any
    # evidence was listed, not because the row vanished.
    pending_evidence.refresh_from_db()
    assert pending_evidence.review_status == Evidence.ReviewStatus.PENDING
