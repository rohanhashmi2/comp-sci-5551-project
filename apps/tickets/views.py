from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from apps.accounts.models import User
from apps.common.mixins import InspectorRequiredMixin, OwnerRequiredMixin
from apps.inspections.models import InspectionResult

from .forms import EvidenceForm, EvidenceReviewForm
from .models import Evidence, Ticket

TEMPLATE_NAME = "tickets/ticket_detail.html"


def _evidence_prefix(result):
    return f"evidence-{result.pk}"


def _review_prefix(evidence):
    return f"review-{evidence.pk}"


def _violation_url(ticket, result):
    return f"{reverse('tickets:detail', args=[ticket.pk])}#violation-{result.pk}"


def _form(form_class, prefix, bound_form):
    """Return ``bound_form`` if it belongs at ``prefix``, else a blank form."""
    if bound_form is not None and bound_form.prefix == prefix:
        return bound_form
    return form_class(prefix=prefix)


def _render_ticket(request, ticket, bound_form=None):
    """Render the ticket page for either role.

    Owners get an evidence form under each unresolved violation;
    inspectors get a review form under each pending evidence row.
    ``bound_form`` is a submission that failed validation. It takes the
    place of the blank form with the same prefix, so its errors show on
    the row they belong to.
    """
    violations = list(
        ticket.violations().prefetch_related(
            Prefetch(
                "evidence", queryset=Evidence.objects.all(), to_attr="evidence_list"
            )
        )
    )
    role = request.user.role
    for violation in violations:
        if role == User.Role.OWNER and not violation.is_resolved:
            violation.evidence_form = _form(
                EvidenceForm, _evidence_prefix(violation), bound_form
            )
        for evidence in violation.evidence_list:
            if (
                role == User.Role.INSPECTOR
                and evidence.review_status == Evidence.ReviewStatus.PENDING
            ):
                evidence.review_form = _form(
                    EvidenceReviewForm, _review_prefix(evidence), bound_form
                )
    return render(
        request,
        TEMPLATE_NAME,
        {"ticket": ticket, "status": ticket.status, "violations": violations},
    )


class TicketDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        ticket = get_object_or_404(
            Ticket.objects.visible_to(request.user).select_related(
                "inspection__store__owner"
            ),
            pk=pk,
        )
        return _render_ticket(request, ticket)


class EvidenceCreateView(LoginRequiredMixin, OwnerRequiredMixin, View):
    def post(self, request, result_pk):
        # Scoped through visible_to, so another owner's violation is a 404.
        result = get_object_or_404(
            InspectionResult.objects.visible_to(request.user).filter(
                outcome=InspectionResult.Outcome.FAIL,
                inspection__ticket__isnull=False,
            ),
            pk=result_pk,
        )
        ticket = result.inspection.ticket
        form = EvidenceForm(
            request.POST, request.FILES, prefix=_evidence_prefix(result)
        )
        if not form.is_valid():
            return _render_ticket(request, ticket, bound_form=form)

        form.instance.result = result
        form.instance.submitted_by = request.user
        form.save()
        messages.success(request, "Evidence submitted for review.")
        return redirect(_violation_url(ticket, result))


class EvidenceReviewView(LoginRequiredMixin, InspectorRequiredMixin, View):
    def post(self, request, pk):
        evidence = get_object_or_404(
            Evidence.objects.visible_to(request.user).select_related(
                "result__inspection__ticket"
            ),
            pk=pk,
        )
        ticket = evidence.result.inspection.ticket
        form = EvidenceReviewForm(
            request.POST, instance=evidence, prefix=_review_prefix(evidence)
        )
        if not form.is_valid():
            return _render_ticket(request, ticket, bound_form=form)

        form.instance.reviewed_at = timezone.now()
        form.save()
        messages.success(
            request, f"Evidence {evidence.get_review_status_display().lower()}."
        )
        return redirect(_violation_url(ticket, evidence.result))
