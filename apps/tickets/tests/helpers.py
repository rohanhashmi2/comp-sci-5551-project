"""Builders shared by the ticket and store-history tests.

Story 9 (submit inspection and issue ticket) is not built yet, so these
create completed inspections and tickets directly through the ORM.
"""

import io
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from apps.inspections.models import ChecklistItem, Inspection, InspectionResult
from apps.tickets.models import Ticket

ITEM_TITLES = [
    "Cold holding temperature",
    "Hand-washing sink stocked",
    "Raw meat stored below ready-to-eat food",
    "Pest control log current",
]


def make_image(name="photo.png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


def make_checklist_items():
    return [
        ChecklistItem.objects.create(
            code=f"TS-{i:02d}",
            title=title,
            description="Standard text.",
            ordering=i,
        )
        for i, title in enumerate(ITEM_TITLES, start=1)
    ]


def make_inspection(store, items, outcomes, *, days_ago=1):
    """A completed inspection with one result per (item, outcome) pair.

    Failed results carry a comment and a photo, as Stories 7 and 8 require.
    """
    inspection = Inspection.objects.create(
        store=store,
        scheduled_for=timezone.now() - timedelta(days=days_ago),
        status=Inspection.Status.COMPLETED,
    )
    for item, outcome in zip(items, outcomes):
        failed = outcome == InspectionResult.Outcome.FAIL
        InspectionResult.objects.create(
            inspection=inspection,
            checklist_item=item,
            outcome=outcome,
            comment=f"{item.title} not met." if failed else "",
            photo=make_image(f"{item.code}.png") if failed else None,
        )
    return inspection


def issue_ticket(inspection, *, days_until_deadline=14):
    return Ticket.objects.create(
        inspection=inspection,
        deadline=timezone.localdate() + timedelta(days=days_until_deadline),
    )
