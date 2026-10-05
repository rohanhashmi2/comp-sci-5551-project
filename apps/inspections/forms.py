from django import forms
from django.forms.models import BaseModelFormSet
from django.utils import timezone

from .models import Inspection, InspectionResult


class InspectionScheduleForm(forms.ModelForm):
    class Meta:
        model = Inspection
        fields = ("store", "scheduled_for")
        widgets = {
            "scheduled_for": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["store"].empty_label = "Choose a store…"

    def clean_scheduled_for(self):
        value = self.cleaned_data["scheduled_for"]
        if value <= timezone.now():
            raise forms.ValidationError(
                "The date must be in the future.", code="not_future"
            )
        return value


class InspectionResultForm(forms.ModelForm):
    """One row of the conducting formset.

    Only ``outcome`` is editable in Story 6. Dev 2's Stories 7 and 8
    extend ``Meta.fields`` with ``comment`` and ``photo`` and add a
    per-form ``clean`` enforcing those-are-required-when-FAIL.
    """

    # Override the auto-generated field to drop the blank option. By
    # default ModelForm adds ("", "---------") to the choices of any
    # CharField(choices=...) without a default, which (a) muddies the
    # AC 6.1 "offers pass, fail, and not applicable" assertion and
    # (b) lets an empty POST validate as "chose blank" instead of
    # tripping required=True. We want the empty case to raise.
    outcome = forms.ChoiceField(
        choices=InspectionResult.Outcome.choices,
        widget=forms.RadioSelect,
        required=True,
    )

    class Meta:
        model = InspectionResult
        fields = ("outcome",)


class BaseInspectionResultFormSet(BaseModelFormSet):
    """Formset-level validation for the conducting form.

    Each row's ``outcome`` is required by the per-form ChoiceField, so
    missing outcomes produce per-form errors. This ``clean`` adds two
    additional guards:

    1. A form-count check (anti-tamper): the number of submitted forms
       must equal ``self.expected_count``, which the view attaches
       before calling ``is_valid``.
    2. A formset-level non-form error listing the unmarked codes so
       the template shows a single banner instead of forcing the
       inspector to hunt rows.
    """

    def clean(self):
        super().clean()
        expected = getattr(self, "expected_count", None)
        actual = self.total_form_count()
        if expected is not None and actual != expected:
            raise forms.ValidationError(
                f"Expected {expected} rows, got {actual}.",
                code="form_count_mismatch",
            )
        missing_codes = []
        for form in self.forms:
            if form.errors.get("outcome"):
                item = getattr(form, "checklist_item_obj", None)
                if item is not None:
                    missing_codes.append(item.code)
        if missing_codes:
            raise forms.ValidationError(
                f"These items need an outcome: {', '.join(missing_codes)}.",
                code="incomplete",
            )
