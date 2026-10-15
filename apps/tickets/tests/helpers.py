"""Builders shared by the ticket and store-history tests.

``make_inspection`` produces what Story 9's conduct view leaves behind:
an IN_PROGRESS inspection with one result per item, and one ticket per
failed result carrying the result's comment, photo and deadline.
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


def make_inspection(store, items, outcomes, *, inspector, days_ago=1):
    inspection = Inspection.objects.create(
        store=store,
        scheduled_for=timezone.now() - timedelta(days=days_ago),
        status=Inspection.Status.IN_PROGRESS,
        started_at=timezone.now() - timedelta(days=days_ago),
    )
    for item, outcome in zip(items, outcomes):
        if outcome != InspectionResult.Outcome.FAIL:
            InspectionResult.objects.create(
                inspection=inspection, checklist_item=item, outcome=outcome
            )
            continue
        result = InspectionResult.objects.create(
            inspection=inspection,
            checklist_item=item,
            outcome=outcome,
            comment=f"{item.title} not met.",
            photo=make_image(f"{item.code}.png"),
            deadline=timezone.now() + timedelta(days=14),
        )
        Ticket.objects.create(
            inspection=inspection,
            inspection_result=result,
            store=store,
            created_by=inspector,
            title=f"Failed Inspection Item: {item.code}",
            description=result.comment,
        )
    return inspection
