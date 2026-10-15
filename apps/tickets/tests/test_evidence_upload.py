import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.tickets.models import Evidence, Ticket

from .helpers import make_image


def _upload_url(ticket):
    return reverse("tickets:evidence_create", args=[ticket.pk])


def _post_data(photo=None, note="Thermometer recalibrated."):
    data = {"note": note}
    if photo is not None:
        data["photo"] = photo
    return data


@pytest.mark.django_db
def test_ac12_01_evidence_uploaded_against_violation(logged_in_owner, owner, ticket):
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
        _upload_url(ticket), data=_post_data(photo=make_image("fix.png")), follow=True
    )

    assert response.status_code == 200
    detail_url = reverse("tickets:detail", args=[ticket.pk])
    assert response.redirect_chain[-1][0] == detail_url

    evidence = Evidence.objects.get()
    assert evidence.ticket == ticket
    assert evidence.submitted_by == owner
    assert evidence.review_status == Evidence.ReviewStatus.PENDING
    assert evidence.note == "Thermometer recalibrated."

    assert response.context["evidence_list"] == [evidence]
    assert evidence.photo.url.encode() in response.content
    assert b"Thermometer recalibrated." in response.content


@pytest.mark.django_db
def test_ac12_02_upload_without_file_rejected(logged_in_owner, ticket):
    """
    AC 12.2 — Upload rejected when no file is attached

    Given a store owner is viewing a violation on their open ticket
    When the store owner submits the evidence form with no file attached
    Then the system does not store the evidence and displays an error
      message stating a photo is required
    """
    response = logged_in_owner.post(_upload_url(ticket), data=_post_data())

    assert response.status_code == 200
    assert Evidence.objects.count() == 0
    form = response.context["evidence_form"]
    assert form.errors["photo"] == ["A photo is required."]
    assert b"A photo is required." in response.content


@pytest.mark.django_db
def test_ac12_03_non_image_file_rejected(logged_in_owner, ticket):
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
        _upload_url(ticket), data=_post_data(photo=not_an_image)
    )

    assert response.status_code == 200
    assert Evidence.objects.count() == 0
    form = response.context["evidence_form"]
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
    response = logged_in_owner.post(
        _upload_url(other_ticket), data=_post_data(photo=make_image())
    )

    assert response.status_code == 404
    assert Evidence.objects.count() == 0


@pytest.mark.django_db
def test_inspector_cannot_upload_evidence(logged_in_inspector, ticket):
    """Supporting test: evidence upload is owner-only."""
    response = logged_in_inspector.post(
        _upload_url(ticket), data=_post_data(photo=make_image())
    )

    assert response.status_code == 302
    assert response.url == reverse("home")
    assert Evidence.objects.count() == 0


@pytest.mark.django_db
def test_evidence_form_hidden_once_ticket_resolved(logged_in_owner, ticket):
    """Supporting test: the upload form is only offered on an open ticket."""
    ticket.status = Ticket.Status.RESOLVED
    ticket.save()

    response = logged_in_owner.get(reverse("tickets:detail", args=[ticket.pk]))

    assert response.context["evidence_form"] is None
    assert _upload_url(ticket).encode() not in response.content
