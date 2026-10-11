import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.tickets.models import Evidence

from .helpers import make_image


def _upload_url(result):
    return reverse("tickets:evidence_create", args=[result.pk])


def _post_data(result, photo=None, note="Thermometer recalibrated."):
    prefix = f"evidence-{result.pk}"
    data = {f"{prefix}-note": note}
    if photo is not None:
        data[f"{prefix}-photo"] = photo
    return data


def _form_on_page(response, result):
    violation = next(v for v in response.context["violations"] if v.pk == result.pk)
    return violation.evidence_form


@pytest.mark.django_db
def test_ac12_01_evidence_uploaded_against_violation(
    logged_in_owner, owner, ticket, violation
):
    """
    AC 12.1 — Evidence uploaded against a violation

    Given a store owner is logged in and an open ticket against their store
      contains a failed item
    When the store owner attaches a valid image and a note to that item and
      submits
    Then the system stores the evidence against that violation with review
      status pending and the evidence is displayed under that violation
    """
    response = logged_in_owner.post(
        _upload_url(violation),
        data=_post_data(violation, photo=make_image("fix.png")),
        follow=True,
    )

    assert response.status_code == 200
    detail_url = reverse("tickets:detail", args=[ticket.pk])
    assert response.redirect_chain[-1][0] == f"{detail_url}#violation-{violation.pk}"

    evidence = Evidence.objects.get()
    assert evidence.result == violation
    assert evidence.submitted_by == owner
    assert evidence.review_status == Evidence.ReviewStatus.PENDING
    assert evidence.note == "Thermometer recalibrated."

    shown = next(v for v in response.context["violations"] if v.pk == violation.pk)
    assert shown.evidence_list == [evidence]
    assert evidence.photo.url.encode() in response.content
    assert b"Thermometer recalibrated." in response.content


@pytest.mark.django_db
def test_ac12_02_upload_without_file_rejected(logged_in_owner, violation):
    """
    AC 12.2 — Upload rejected when no file is attached

    Given a store owner is viewing a violation on their open ticket
    When the store owner submits the evidence form with no file attached
    Then the system does not store the evidence and displays an error
      message stating a photo is required
    """
    response = logged_in_owner.post(_upload_url(violation), data=_post_data(violation))

    assert response.status_code == 200
    assert Evidence.objects.count() == 0
    form = _form_on_page(response, violation)
    assert form.errors["photo"] == ["A photo is required."]
    assert b"A photo is required." in response.content


@pytest.mark.django_db
def test_ac12_03_non_image_file_rejected(logged_in_owner, violation):
    """
    AC 12.3 — Upload rejected for a file that is not an image

    Given a store owner is viewing a violation on their open ticket
    When the store owner attaches a file that is not an image and submits
    Then the system does not store the evidence and displays an error
      message stating the file must be an image
    """
    not_an_image = SimpleUploadedFile(
        "notes.txt", b"just some text", content_type="text/plain"
    )

    response = logged_in_owner.post(
        _upload_url(violation), data=_post_data(violation, photo=not_an_image)
    )

    assert response.status_code == 200
    assert Evidence.objects.count() == 0
    form = _form_on_page(response, violation)
    assert form.errors["photo"] == ["The file must be an image."]
    assert b"The file must be an image." in response.content


@pytest.mark.django_db
def test_ac12_04_owner_cannot_upload_to_other_owners_violation(
    logged_in_owner, other_ticket
):
    """
    AC 12.4 — Owner cannot upload evidence against another owner's violation

    Given a store owner is logged in and a violation exists on a ticket
      belonging to a different owner
    When the store owner submits evidence against that violation
    Then the system responds with not found and no evidence is stored
    """
    their_violation = other_ticket.violations().first()

    response = logged_in_owner.post(
        _upload_url(their_violation),
        data=_post_data(their_violation, photo=make_image()),
    )

    assert response.status_code == 404
    assert Evidence.objects.count() == 0


@pytest.mark.django_db
def test_inspector_cannot_upload_evidence(logged_in_inspector, violation):
    """Supporting test: evidence upload is owner-only."""
    response = logged_in_inspector.post(
        _upload_url(violation), data=_post_data(violation, photo=make_image())
    )

    assert response.status_code == 302
    assert response.url == reverse("home")
    assert Evidence.objects.count() == 0


@pytest.mark.django_db
def test_upload_against_passed_result_returns_404(logged_in_owner, ticket):
    """Supporting test: only failed results on a ticket accept evidence."""
    passed = ticket.inspection.results.get(outcome="PASS")

    response = logged_in_owner.post(
        _upload_url(passed), data=_post_data(passed, photo=make_image())
    )

    assert response.status_code == 404
    assert Evidence.objects.count() == 0
