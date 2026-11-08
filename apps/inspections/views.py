from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.forms import modelformset_factory
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView

from apps.common.mixins import InspectorRequiredMixin

from . import transitions
from .forms import (
    BaseInspectionResultFormSet,
    InspectionResultForm,
    InspectionScheduleForm,
    InspectionSubmitForm,
)
from .models import ChecklistItem, Inspection, InspectionResult
from apps.tickets.models import Ticket


class InspectionCreateView(LoginRequiredMixin, InspectorRequiredMixin, CreateView):
    model = Inspection
    form_class = InspectionScheduleForm
    template_name = "inspections/inspection_form.html"
    success_url = reverse_lazy("accounts:inspector_dashboard")

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request,
            f"Inspection scheduled for {form.instance.store.name}.",
        )
        return response


class InspectionConductView(LoginRequiredMixin, InspectorRequiredMixin, View):
    template_name = "inspections/inspection_conduct.html"

    def _get_inspection(self):
        return get_object_or_404(Inspection, pk=self.kwargs["pk"])

    def _active_items(self):
        return list(ChecklistItem.objects.filter(is_active=True))

    def _build_formset(self, data=None, files=None):
        active = self._active_items()
        FormSetCls = modelformset_factory(  # noqa: N806  (Django idiom)
            InspectionResult,
            form=InspectionResultForm,
            formset=BaseInspectionResultFormSet,
            extra=len(active),
            max_num=len(active),
            validate_max=True,
            # Deliberately not using validate_min / min_num. Django's
            # min-check counts an unchanged-data form as "empty" and
            # raises a generic "please submit at least N forms" error
            # that masks our AC 6.3 message. The formset's own clean()
            # enforces exact length via expected_count below.
            can_delete=False,
        )
        formset = FormSetCls(
            data=data,
            files=files,
            queryset=InspectionResult.objects.none(),
            # Every row is required. Without this, Django treats extras
            # with no changed data as "empty, no problem" and skips the
            # required check on outcome — defeating AC 6.3.
            form_kwargs={"empty_permitted": False},
        )
        formset.expected_count = len(active)
        # Attach the ChecklistItem instance to each form so the template
        # can render its code/title/description and the formset's clean()
        # can list the missing codes by inspecting form.checklist_item_obj.
        for form, item in zip(formset.forms, active):
            form.checklist_item_obj = item
        return formset, active

    def get(self, request, *args, **kwargs):
        inspection = self._get_inspection()
        formset, active = self._build_formset()
        return render(
            request,
            self.template_name,
            {
                "inspection": inspection,
                "formset": formset,
                "active_items": active,
            },
        )

    def post(self, request, *args, **kwargs):
        inspection = self._get_inspection()
        if inspection.status != Inspection.Status.SCHEDULED:
            messages.error(
                request,
                "This inspection has already been recorded. "
                "Open a new inspection to record another visit.",
            )
            return redirect("accounts:inspector_dashboard")

        formset, active = self._build_formset(
            data=request.POST,
            files=request.FILES,
        )
        if not formset.is_valid():
            return render(
                request,
                self.template_name,
                {
                    "inspection": inspection,
                    "formset": formset,
                    "active_items": active,
                },
            )

        with transaction.atomic():
            for form, item in zip(formset.forms, active):
                result = InspectionResult.objects.create(
                    inspection=inspection,
                    checklist_item=item,
                    outcome=form.cleaned_data["outcome"],
                    comment=form.cleaned_data["comment"],
                    photo=form.cleaned_data["photo"],
                    deadline=form.cleaned_data["deadline"],
                )

                if result.outcome == InspectionResult.Outcome.FAIL:
                    Ticket.objects.create(
                        inspection=inspection,
                        inspection_result=result,
                        store=inspection.store,
                        created_by=request.user,
                        title=f"Failed Inspection Item: {item.code}",
                        description=result.comment,
                    )

            transitions.apply(inspection, "begin")
            inspection.started_at = timezone.now()
            inspection.save(update_fields=["status", "started_at"])

        messages.success(request, "Inspection recorded.")
        return redirect("accounts:inspector_dashboard")


class InspectionSubmitView(LoginRequiredMixin, InspectorRequiredMixin, View):
    """Terminal step: inspector adds closing notes and marks COMPLETED.

    The checklist results and any Tickets are already created by
    ``InspectionConductView.post``, which lands the inspection at
    IN_PROGRESS. This view only advances the status and records the
    inspector's overall assessment. Rejects on any status other than
    IN_PROGRESS; a repeat submit on a COMPLETED row keeps the original
    ``completed_at`` and ``notes`` unchanged.
    """

    template_name = "inspections/inspection_submit.html"

    def _get_inspection(self):
        return get_object_or_404(Inspection, pk=self.kwargs["pk"])

    def _reject_if_not_in_progress(self, request, inspection):
        if inspection.status == Inspection.Status.COMPLETED:
            messages.error(request, "This inspection has already been submitted.")
            return redirect("accounts:inspector_dashboard")
        if inspection.status != Inspection.Status.IN_PROGRESS:
            messages.error(
                request,
                "This inspection cannot be submitted in its current state.",
            )
            return redirect("accounts:inspector_dashboard")
        return None

    def get(self, request, *args, **kwargs):
        inspection = self._get_inspection()
        rejected = self._reject_if_not_in_progress(request, inspection)
        if rejected is not None:
            return rejected
        return render(
            request,
            self.template_name,
            {"inspection": inspection, "form": InspectionSubmitForm()},
        )

    def post(self, request, *args, **kwargs):
        inspection = self._get_inspection()
        rejected = self._reject_if_not_in_progress(request, inspection)
        if rejected is not None:
            return rejected

        form = InspectionSubmitForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"inspection": inspection, "form": form},
            )

        with transaction.atomic():
            transitions.apply(inspection, "submit")
            inspection.notes = form.cleaned_data["notes"]
            inspection.completed_at = timezone.now()
            inspection.save(update_fields=["status", "notes", "completed_at"])

        messages.success(request, "Inspection submitted.")
        return redirect("accounts:inspector_dashboard")
