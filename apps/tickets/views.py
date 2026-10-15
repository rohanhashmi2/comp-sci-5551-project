from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from apps.accounts.models import User
from apps.common.mixins import InspectorRequiredMixin, OwnerRequiredMixin

from .forms import EvidenceForm, EvidenceReviewForm
from .models import Evidence, Ticket

TEMPLATE_NAME = "tickets/ticket_detail.html"


class OwnerTicketListView(LoginRequiredMixin, ListView):
    model = Ticket
    template_name = "tickets/owner_ticket_list.html"
    context_object_name = "tickets"

    def get_queryset(self):
        return Ticket.objects.filter(
            store__owner=self.request.user,
            status=Ticket.Status.OPEN,
        )


def _review_prefix(evidence):
    return f"review-{evidence.pk}"


def _render_ticket(request, ticket, bound_form=None):
    """Render the ticket page for either role.

    Owners get an evidence form while the ticket is open; inspectors get
    a review form under each pending evidence row. ``bound_form`` is a
    submission that failed validation and replaces the blank form it
    stands for, so its errors show where it was filled in.
    """
    evidence_list = list(ticket.evidence.all())
    evidence_form = None
    if request.user.role == User.Role.OWNER and ticket.status == Ticket.Status.OPEN:
        if isinstance(bound_form, EvidenceForm):
            evidence_form = bound_form
        else:
            evidence_form = EvidenceForm()
    if request.user.role == User.Role.INSPECTOR:
        for evidence in evidence_list:
            if evidence.review_status != Evidence.ReviewStatus.PENDING:
                continue
            prefix = _review_prefix(evidence)
            if (
                isinstance(bound_form, EvidenceReviewForm)
                and bound_form.prefix == prefix
            ):
                evidence.review_form = bound_form
            else:
                evidence.review_form = EvidenceReviewForm(prefix=prefix)
    return render(
        request,
        TEMPLATE_NAME,
        {
            "ticket": ticket,
            "result": ticket.inspection_result,
            "evidence_list": evidence_list,
            "evidence_form": evidence_form,
        },
    )


def _scoped_ticket(request, pk):
    # Scoped through visible_to, so another owner's ticket is a 404.
    return get_object_or_404(
        Ticket.objects.visible_to(request.user).select_related(
            "store__owner", "inspection", "inspection_result__checklist_item"
        ),
        pk=pk,
    )


class TicketDetailView(LoginRequiredMixin, View):
    def get(self, request, pk):
        return _render_ticket(request, _scoped_ticket(request, pk))


class EvidenceCreateView(LoginRequiredMixin, OwnerRequiredMixin, View):
    def post(self, request, pk):
        ticket = _scoped_ticket(request, pk)
        form = EvidenceForm(request.POST, request.FILES)
        if not form.is_valid():
            return _render_ticket(request, ticket, bound_form=form)

        form.instance.ticket = ticket
        form.instance.submitted_by = request.user
        form.save()
        messages.success(request, "Evidence submitted for review.")
        return redirect("tickets:detail", pk=ticket.pk)


class EvidenceReviewView(LoginRequiredMixin, InspectorRequiredMixin, View):
    def post(self, request, pk):
        evidence = get_object_or_404(
            Evidence.objects.visible_to(request.user).select_related("ticket"),
            pk=pk,
        )
        ticket = evidence.ticket
        form = EvidenceReviewForm(
            request.POST, instance=evidence, prefix=_review_prefix(evidence)
        )
        if not form.is_valid():
            return _render_ticket(request, ticket, bound_form=form)

        with transaction.atomic():
            form.instance.reviewed_at = timezone.now()
            form.save()
            if evidence.review_status == Evidence.ReviewStatus.ACCEPTED:
                ticket.status = Ticket.Status.RESOLVED
                ticket.save(update_fields=["status"])
        messages.success(
            request, f"Evidence {evidence.get_review_status_display().lower()}."
        )
        return redirect(f"{reverse('tickets:detail', args=[ticket.pk])}#evidence")
