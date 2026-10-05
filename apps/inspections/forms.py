from django import forms
from django.utils import timezone

from .models import Inspection


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
