import pytest
from django.urls import reverse

from apps.tickets.models import Evidence


def _review_url(evidence):
    return reverse("tickets:evidence_review", args=[evidence.pk])


def _post_data(evidence, decision, comment=""):
    prefix = f"review-{evidence.pk}"
    return {f"{prefix}-review_status": decision, f"{prefix}-reviewer_comment": comment}


def _violation_on_page(response, evidence):
    return next(v for v in response.context["violations"] if v.pk == evidence.result_id)


@pytest.mark.django_db
def test_ac13_01_inspector_accepts_evidence(logged_in_inspector, pending_evidence):
    """
    AC 13.1 — Inspector accepts evidence

    Given an inspector is logged in and evidence has been submitted against
      a violation on their inspection
    When the inspector marks that evidence as accepted
    Then the system records the review status as accepted with the review
      time and the violation is shown as resolved
    """
    response = logged_in_inspector.post(
        _review_url(pending_evidence),
        data=_post_data(pending_evidence, "ACCEPTED"),
        follow=True,
    )

    assert response.status_code == 200
    pending_evidence.refresh_from_db()
    assert pending_evidence.review_status == Evidence.ReviewStatus.ACCEPTED
    assert pending_evidence.reviewed_at is not None

    violation = _violation_on_page(response, pending_evidence)
    assert violation.is_resolved is True
    assert "✓ Resolved".encode() in response.content


@pytest.mark.django_db
def test_ac13_02_inspector_rejects_evidence_with_comment(
    logged_in_inspector, pending_evidence
):
    """
    AC 13.2 — Inspector rejects evidence with a comment

    Given an inspector is logged in and evidence has been submitted against
      a violation on their inspection
    When the inspector marks that evidence as rejected and enters a comment
    Then the system records the review status as rejected with that comment
      and the violation remains unresolved
    """
    comment = "Photo does not show the thermometer reading."

    response = logged_in_inspector.post(
        _review_url(pending_evidence),
        data=_post_data(pending_evidence, "REJECTED", comment),
        follow=True,
    )

    assert response.status_code == 200
    pending_evidence.refresh_from_db()
    assert pending_evidence.review_status == Evidence.ReviewStatus.REJECTED
    assert pending_evidence.reviewer_comment == comment
    assert pending_evidence.reviewed_at is not None

    violation = _violation_on_page(response, pending_evidence)
    assert violation.is_resolved is False
    assert comment.encode() in response.content


@pytest.mark.django_db
def test_ac13_03_rejection_without_comment_rejected(
    logged_in_inspector, pending_evidence
):
    """
    AC 13.3 — Rejection rejected when no comment is given

    Given an inspector is reviewing submitted evidence
    When the inspector marks the evidence as rejected with the comment field
      left empty
    Then the system does not record the review and displays an error
      message stating a comment is required when rejecting
    """
    response = logged_in_inspector.post(
        _review_url(pending_evidence),
        data=_post_data(pending_evidence, "REJECTED", ""),
    )

    assert response.status_code == 200
    pending_evidence.refresh_from_db()
    assert pending_evidence.review_status == Evidence.ReviewStatus.PENDING
    assert pending_evidence.reviewed_at is None

    violation = _violation_on_page(response, pending_evidence)
    form = violation.evidence_list[0].review_form
    assert form.has_error("reviewer_comment", code="comment_required")
    assert b"A comment is required when rejecting evidence." in response.content


@pytest.mark.django_db
def test_ac13_04_owner_cannot_review_evidence(logged_in_owner, pending_evidence):
    """
    AC 13.4 — A store owner cannot review evidence

    Given a store owner is logged in and evidence has been submitted against
      a violation on their ticket
    When the store owner submits a review decision for that evidence
    Then the system denies access and no review is recorded
    """
    response = logged_in_owner.post(
        _review_url(pending_evidence),
        data=_post_data(pending_evidence, "ACCEPTED"),
    )

    assert response.status_code == 302
    assert response.url == reverse("home")
    pending_evidence.refresh_from_db()
    assert pending_evidence.review_status == Evidence.ReviewStatus.PENDING
    assert pending_evidence.reviewed_at is None


@pytest.mark.django_db
def test_review_form_shown_to_inspector_only(
    client, inspector, owner, ticket, pending_evidence
):
    """Supporting test: the review form renders for inspectors, not owners."""
    url = reverse("tickets:detail", args=[ticket.pk])

    client.force_login(inspector)
    inspector_page = client.get(url)
    assert (
        _violation_on_page(inspector_page, pending_evidence)
        .evidence_list[0]
        .review_form
    )
    assert _review_url(pending_evidence).encode() in inspector_page.content

    client.force_login(owner)
    owner_page = client.get(url)
    assert _review_url(pending_evidence).encode() not in owner_page.content
