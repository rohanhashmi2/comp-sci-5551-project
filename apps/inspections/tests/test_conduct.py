import io
from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.accounts.models import User
from apps.inspections.models import ChecklistItem, Inspection, InspectionResult
from apps.stores.models import Store
from apps.tickets.models import Ticket

INSPECTOR_DASHBOARD_URL = reverse("accounts:inspector_dashboard")


def _conduct_url(inspection):
    return reverse("inspections:conduct", args=[inspection.pk])


def _make_image(name="photo.png"):
    """Minimal in-memory PNG sufficient to pass ImageField validation."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")



def _make_oversized_image():
    """Create a valid PNG upload exceeding the 5 MB limit."""
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")

    image_content = buffer.getvalue()

    oversized_content = (
        image_content
        + b"\x00" * (5 * 1024 * 1024 + 1 - len(image_content))
    )

    return SimpleUploadedFile(
        "oversized.png",
        oversized_content,
        content_type="image/png",
    )



# def _formset_post_data(outcomes):
#     """Build the POST payload for the InspectionResult formset.

#     ``outcomes`` is a list of outcome strings in checklist-item order.
#     An empty string ``""`` simulates an unmarked radio.

#     FAIL rows auto-carry the comment, photo and future deadline that
#     ``InspectionResultForm.clean`` requires since Stories 7–9. PASS and
#     NOT_APPLICABLE rows carry only an outcome.
#     """
#     deadline = timezone.localdate() + timedelta(days=14)
#     deadline_str = deadline.strftime("%Y-%m-%d")
#     data = {
#         "form-TOTAL_FORMS": str(len(outcomes)),
#         "form-INITIAL_FORMS": "0",
#         "form-MIN_NUM_FORMS": str(len(outcomes)),
#         "form-MAX_NUM_FORMS": str(len(outcomes)),
#     }
#     for i, outcome in enumerate(outcomes):
#         data[f"form-{i}-id"] = ""
#         data[f"form-{i}-outcome"] = outcome
#         if outcome == "FAIL":
#             data[f"form-{i}-comment"] = f"Item {i + 1} not met."
#             data[f"form-{i}-photo"] = _make_image(f"item-{i + 1}.png")
#             data[f"form-{i}-deadline"] = deadline_str
#     return data


def _formset_post_data(
    outcomes,
    comments=None,
    include_photos=True,
    include_deadlines=True,
):
    """Build POST data for the InspectionResult formset."""
    deadline = timezone.localdate() + timedelta(days=14)

    data = {
        "form-TOTAL_FORMS": str(len(outcomes)),
        "form-INITIAL_FORMS": "0",
        "form-MIN_NUM_FORMS": "0",
        "form-MAX_NUM_FORMS": str(len(outcomes)),
    }

    for i, outcome in enumerate(outcomes):
        data[f"form-{i}-id"] = ""
        data[f"form-{i}-outcome"] = outcome

        if outcome == "FAIL":
            if isinstance(comments, dict):
                comment = comments.get(i, f"Item {i + 1} not met.")
            elif comments is not None:
                comment = comments[i]
            else:
                comment = f"Item {i + 1} not met."

            data[f"form-{i}-comment"] = comment

            if include_photos:
                data[f"form-{i}-photo"] = _make_image(
                    f"item-{i + 1}.png"
                )

            if include_deadlines:
                data[f"form-{i}-deadline"] = deadline.strftime("%Y-%m-%d")

    return data


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    """Sandbox FAIL-row photo uploads to a per-test tmp dir."""
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def inspector(db):
    return User.objects.create_user(
        email="inspector@example.com",
        password="pw-does-not-matter",
        role=User.Role.INSPECTOR,
    )


@pytest.fixture
def owner(db):
    return User.objects.create_user(
        email="owner@example.com",
        password="pw-does-not-matter",
        role=User.Role.OWNER,
    )


@pytest.fixture
def store(owner):
    return Store.objects.create(name="Corner Market", address="1 Main St", owner=owner)


@pytest.fixture
def scheduled_inspection(store):
    return Inspection.objects.create(
        store=store,
        scheduled_for=timezone.now() + timedelta(days=1),
    )


@pytest.fixture
def logged_in_inspector(client, inspector):
    client.force_login(inspector)
    return client


@pytest.fixture
def logged_in_owner(client, owner):
    client.force_login(owner)
    return client


@pytest.mark.django_db
def test_ac06_01_form_renders_every_active_item(
    logged_in_inspector, scheduled_inspection, checklist_items
):
    """
    AC 6.1 — Checklist renders every active item

    Given an inspector is logged in and an inspection is scheduled
    When the inspector opens the inspection form
    Then one row is displayed per active checklist item and each row
      offers pass, fail, and not applicable
    """
    response = logged_in_inspector.get(_conduct_url(scheduled_inspection))

    assert response.status_code == 200
    formset = response.context["formset"]
    assert len(formset.forms) == len(checklist_items)
    rendered_codes = [f.checklist_item_obj.code for f in formset.forms]
    assert rendered_codes == [item.code for item in checklist_items]
    first_form = formset.forms[0]
    choice_values = {value for value, _ in first_form.fields["outcome"].choices}
    assert choice_values == {"PASS", "FAIL", "NOT_APPLICABLE"}


@pytest.mark.django_db
def test_ac06_02_all_outcomes_recorded_and_status_in_progress(
    logged_in_inspector, scheduled_inspection, checklist_items
):
    """
    AC 6.2 — Recording outcomes for every item

    Given an inspector has the inspection form open
    When the inspector marks every checklist item as pass, fail, or not
      applicable and saves
    Then the system records one result for each checklist item and the
      inspection status becomes in progress
    """
    # Mix outcomes so this test also proves non-PASS values survive the save.
    cycle = ["PASS", "FAIL", "NOT_APPLICABLE"]
    outcomes = [cycle[i % 3] for i in range(len(checklist_items))]

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
        follow=True,
    )

    assert response.status_code == 200
    assert response.redirect_chain[-1][0] == INSPECTOR_DASHBOARD_URL

    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.IN_PROGRESS
    assert scheduled_inspection.started_at is not None
    assert scheduled_inspection.results.count() == len(checklist_items)

    saved = {
        r.checklist_item.code: r.outcome for r in scheduled_inspection.results.all()
    }
    expected = {item.code: outcomes[i] for i, item in enumerate(checklist_items)}
    assert saved == expected


@pytest.mark.django_db
def test_ac06_03_missing_outcome_rejected(
    logged_in_inspector, scheduled_inspection, checklist_items
):
    """
    AC 6.3 — Saving rejected when an item has no outcome

    Given an inspector has the inspection form open
    When the inspector saves with at least one checklist item left unmarked
    Then the system does not save the inspection and displays an error
      message identifying the unmarked items
    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[3] = ""  # Leave the fourth item unmarked.

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )

    assert response.status_code == 200
    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.SCHEDULED
    assert scheduled_inspection.started_at is None
    assert InspectionResult.objects.filter(inspection=scheduled_inspection).count() == 0
    formset = response.context["formset"]
    assert any(err.code == "incomplete" for err in formset.non_form_errors().as_data())
    # The unmarked row carries an inline error on the outcome field.
    unmarked_form = formset.forms[3]
    assert "outcome" in unmarked_form.errors


@pytest.mark.django_db
def test_ac06_04_pass_clean_distinguishable_from_unfilled(
    logged_in_inspector, scheduled_inspection, checklist_items
):
    """
    AC 6.4 — A passed inspection is distinguishable from an unfilled one

    Given an inspector has marked every checklist item as pass and saved
    When the inspection is retrieved
    Then a result exists for every checklist item with outcome pass and
      the inspection is not recorded as incomplete
    """
    # Before: unfilled state — SCHEDULED and zero results.
    assert scheduled_inspection.status == Inspection.Status.SCHEDULED
    assert scheduled_inspection.results.count() == 0

    outcomes = ["PASS"] * len(checklist_items)
    logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )

    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.IN_PROGRESS
    assert scheduled_inspection.results.count() == len(checklist_items)
    assert all(
        r.outcome == InspectionResult.Outcome.PASS
        for r in scheduled_inspection.results.all()
    )
    # The "distinguishable from incomplete" invariant: a passed-clean
    # inspection has one result per *active* checklist item.
    active_count = ChecklistItem.objects.filter(is_active=True).count()
    assert scheduled_inspection.results.count() == active_count


@pytest.mark.django_db
def test_conduct_leaves_inspection_in_progress_not_completed(
    logged_in_inspector, scheduled_inspection, checklist_items
):
    """Supporting test for AC 6.2's contract.

    The conduct view must end the inspection at IN_PROGRESS. Submitting
    (US-25) is a separate step with its own view. This guards against a
    future refactor that chains both transitions into the conduct POST,
    which would silently invalidate AC 6.2.
    """
    outcomes = ["PASS"] * len(checklist_items)

    logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )

    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.IN_PROGRESS
    assert scheduled_inspection.status != Inspection.Status.COMPLETED
    assert scheduled_inspection.completed_at is None
    assert scheduled_inspection.notes == ""


@pytest.mark.django_db
def test_ac06_05_owner_cannot_open_conduct_form(
    logged_in_owner, scheduled_inspection, checklist_items
):
    """
    AC 6.5 (rewritten) — A store owner cannot open the inspection form

    Given a store owner is logged in
    When the store owner requests the inspection form for any inspection
    Then the system denies access and no results are recorded

    See design-notes "Note: AC rewording in US-6" for why the original
    "assigned to a different inspector" wording was replaced.
    """
    outcomes = ["PASS"] * len(checklist_items)

    get_response = logged_in_owner.get(_conduct_url(scheduled_inspection))
    assert get_response.status_code == 302
    assert get_response.url == reverse("home")
    assert InspectionResult.objects.count() == 0

    post_response = logged_in_owner.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )
    assert post_response.status_code == 302
    assert post_response.url == reverse("home")
    assert InspectionResult.objects.count() == 0

    scheduled_inspection.refresh_from_db()
    assert scheduled_inspection.status == Inspection.Status.SCHEDULED

# code added for stories 7 and 8:

@pytest.mark.django_db
def test_ac07_01_comment_saved_on_failed_item(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    Story 7: Comment on a failed item

    AC 7.1 Comment saved against a failed item
Given an inspector has marked a checklist item as fail
When the inspector enters a comment on that item and saves
Then the system stores the comment against that checklist result

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"

    comment = "Fire extinguisher is missing."

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(
            outcomes,
            comments={0: comment},
        ),
    )

    assert response.status_code == 302

    result = InspectionResult.objects.get(
        inspection=scheduled_inspection,
        checklist_item=checklist_items[0],
    )

    assert result.outcome == InspectionResult.Outcome.FAIL
    assert result.comment == comment


@pytest.mark.django_db
def test_ac07_02_failed_item_without_comment_rejected(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 7.2 Save rejected when a failed item has no comment
Given an inspector has marked a checklist item as fail
When the inspector saves with the comment field for that item left empty
Then the system does not save the inspection and displays an error message stating a comment is required for failed items

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(
            outcomes,
            comments={0: ""},
        ),
    )

    assert response.status_code == 200

    formset = response.context["formset"]

    assert "comment" in formset.forms[0].errors

    assert InspectionResult.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    scheduled_inspection.refresh_from_db()

    assert scheduled_inspection.status == Inspection.Status.SCHEDULED
    assert scheduled_inspection.started_at is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "outcome",
    [
        InspectionResult.Outcome.PASS,
        InspectionResult.Outcome.NOT_APPLICABLE,
    ],
)
def test_ac07_03_non_failed_item_without_comment_accepted(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
    outcome,
):
    """
   AC 7.3 Comment is not required for a passed item
Given an inspector has marked a checklist item as pass
When the inspector saves with no comment on that item
Then the system saves the result without error

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = outcome

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )

    assert response.status_code == 302

    result = InspectionResult.objects.get(
        inspection=scheduled_inspection,
        checklist_item=checklist_items[0],
    )

    assert result.outcome == outcome
    assert result.comment == ""


@pytest.mark.django_db
def test_ac08_01_photo_saved_on_failed_item(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 8.1 Photo uploaded against a failed item
Given an inspector has marked a checklist item as fail
When the inspector attaches a valid image file to that item and saves
Then the system stores the image against that checklist result and the image is displayed when the result is viewed

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )

    assert response.status_code == 302

    result = InspectionResult.objects.get(
        inspection=scheduled_inspection,
        checklist_item=checklist_items[0],
    )

    assert result.outcome == InspectionResult.Outcome.FAIL
    assert result.photo
    assert result.photo.name.endswith(".png")
    assert result.photo.storage.exists(result.photo.name)



@pytest.mark.django_db
def test_ac08_02_failed_item_without_photo_rejected(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 8.2 Save rejected when a failed item has no photo
Given an inspector has marked a checklist item as fail
When the inspector saves with no file attached to that item
Then the system does not save the inspection and displays an error message stating a photo is required for failed items

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(
            outcomes,
            include_photos=False,
        ),
    )

    assert response.status_code == 200

    formset = response.context["formset"]

    assert "photo" in formset.forms[0].errors

    assert InspectionResult.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    scheduled_inspection.refresh_from_db()

    assert scheduled_inspection.status == Inspection.Status.SCHEDULED


@pytest.mark.django_db
def test_ac08_03_non_image_file_upload_rejected(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 8.3 Upload rejected for a file that is not an image
Given an inspector has marked a checklist item as fail
When the inspector attaches a file that is not an image and saves
Then the system does not save the inspection and displays an error message stating the file must be an image

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"

    data = _formset_post_data(outcomes)

    # Replace the valid image with a non-image file.
    data["form-0-photo"] = SimpleUploadedFile(
        "document.txt",
        b"This is not an image.",
        content_type="text/plain",
    )

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=data,
    )

    assert response.status_code == 200

    formset = response.context["formset"]

    assert "photo" in formset.forms[0].errors

    assert InspectionResult.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    assert Ticket.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    scheduled_inspection.refresh_from_db()

    assert scheduled_inspection.status == Inspection.Status.SCHEDULED




@pytest.mark.django_db
def test_ac08_04_oversized_photo_rejected(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 8.4 Upload rejected for an oversized file
Given an inspector has marked a checklist item as fail
When the inspector attaches an image larger than the permitted size and saves
Then the system does not save the inspection and displays an error message stating the maximum permitted file size

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"

    data = _formset_post_data(outcomes)

    data["form-0-photo"] = _make_oversized_image()

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=data,
    )

    assert response.status_code == 200

    formset = response.context["formset"]

    assert "photo" in formset.forms[0].errors
    assert any(
        "5MB" in error
        for error in formset.forms[0].errors["photo"]
    )

    assert InspectionResult.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    scheduled_inspection.refresh_from_db()

    assert scheduled_inspection.status == Inspection.Status.SCHEDULED

# code for story 9
@pytest.mark.django_db
def test_ac09_01_ticket_created_for_each_failed_item(
    logged_in_inspector,
    inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 9.1 Tickets issued for each failed item
Given an inspector has recorded an inspection with at least one failed item
When the inspector submits the checklist with a correction deadline on each failed item
Then the system creates one ticket per failed item, each carrying that item’s deadline

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"
    outcomes[2] = "FAIL"
    outcomes[4] = "FAIL"

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )

    assert response.status_code == 302

    tickets = Ticket.objects.filter(inspection=scheduled_inspection)

    assert tickets.count() == 3

    for index in [0, 2, 4]:
        result = InspectionResult.objects.get(
            inspection=scheduled_inspection,
            checklist_item=checklist_items[index],
        )

        ticket = tickets.get(inspection_result=result)

        assert ticket.store == scheduled_inspection.store
        assert ticket.created_by == inspector
        assert ticket.status == Ticket.Status.OPEN
        assert ticket.title == (
            f"Failed Inspection Item: {checklist_items[index].code}"
        )
        assert ticket.description == result.comment


@pytest.mark.django_db
def test_ac09_02_no_tickets_created_without_failures(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 9.2 No ticket issued when the inspection has no failures
Given an inspector has completed an inspection with every item marked pass or not applicable
When the inspector submits the inspection
Then the system sets the inspection status to completed and no ticket is created

    """
    outcomes = ["PASS"] * len(checklist_items)

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=_formset_post_data(outcomes),
    )

    assert response.status_code == 302

    assert InspectionResult.objects.filter(
        inspection=scheduled_inspection
    ).count() == len(checklist_items)

    assert Ticket.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    scheduled_inspection.refresh_from_db()

    assert scheduled_inspection.status == Inspection.Status.IN_PROGRESS


@pytest.mark.django_db
def test_ac09_03_failed_item_without_deadline_rejected(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 9.3 Submission rejected when failures exist and no deadline is given
Given an inspector has completed an inspection with at least one failed item
When the inspector submits the inspection with the deadline field left empty
Then the system does not complete the inspection and displays an error message stating a deadline is required

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"

    data = _formset_post_data(outcomes)

    data.pop("form-0-deadline")

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=data,
    )

    assert response.status_code == 200

    formset = response.context["formset"]

    assert "deadline" in formset.forms[0].errors

    assert InspectionResult.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    assert Ticket.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    scheduled_inspection.refresh_from_db()

    assert scheduled_inspection.status == Inspection.Status.SCHEDULED


@pytest.mark.django_db
def test_ac09_04_past_deadline_rejected(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 9.4 Submission rejected for a deadline in the past
Given an inspector has completed an inspection with at least one failed item
When the inspector submits the inspection with a deadline earlier than today
Then the system does not complete the inspection and displays an error message stating the deadline must be in the future

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"

    data = _formset_post_data(outcomes)

    past_deadline = timezone.localdate() - timedelta(days=1)

    data["form-0-deadline"] = past_deadline.strftime("%Y-%m-%d")

    response = logged_in_inspector.post(
        _conduct_url(scheduled_inspection),
        data=data,
    )

    assert response.status_code == 200

    formset = response.context["formset"]

    assert "deadline" in formset.forms[0].errors
    assert any(
        "future" in error.lower()
        for error in formset.forms[0].errors["deadline"]
    )

    assert InspectionResult.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    assert Ticket.objects.filter(
        inspection=scheduled_inspection
    ).count() == 0

    scheduled_inspection.refresh_from_db()

    assert scheduled_inspection.status == Inspection.Status.SCHEDULED


@pytest.mark.django_db
def test_ac09_05_duplicate_inspection_submission_rejected(
    logged_in_inspector,
    scheduled_inspection,
    checklist_items,
):
    """
    AC 9.5 A completed inspection cannot be submitted twice
Given an inspection has already been submitted and is completed
When the inspector submits that inspection again
Then the system rejects the submission and no second ticket is created

    """
    outcomes = ["PASS"] * len(checklist_items)
    outcomes[0] = "FAIL"
    outcomes[1] = "FAIL"

    url = _conduct_url(scheduled_inspection)

    first_response = logged_in_inspector.post(
        url,
        data=_formset_post_data(outcomes),
    )

    assert first_response.status_code == 302

    original_result_count = InspectionResult.objects.filter(
        inspection=scheduled_inspection
    ).count()

    original_ticket_count = Ticket.objects.filter(
        inspection=scheduled_inspection
    ).count()

    assert original_result_count == len(checklist_items)
    assert original_ticket_count == 2

    second_response = logged_in_inspector.post(
        url,
        data=_formset_post_data(outcomes),
        follow=True,
    )

    assert second_response.status_code == 200
    assert second_response.redirect_chain[-1][0] == INSPECTOR_DASHBOARD_URL

    assert InspectionResult.objects.filter(
        inspection=scheduled_inspection
    ).count() == original_result_count

    assert Ticket.objects.filter(
        inspection=scheduled_inspection
    ).count() == original_ticket_count

    scheduled_inspection.refresh_from_db()

    assert scheduled_inspection.status == Inspection.Status.IN_PROGRESS

