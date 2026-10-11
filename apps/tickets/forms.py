from django import forms

from .models import Evidence


class EvidenceForm(forms.ModelForm):
    class Meta:
        model = Evidence
        fields = ("photo", "note")
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}
        error_messages = {
            "photo": {
                "required": "A photo is required.",
                "invalid_image": "The file must be an image.",
            },
        }


class EvidenceReviewForm(forms.ModelForm):
    # Replaces the model field's choices so PENDING cannot be posted back.
    review_status = forms.ChoiceField(
        label="Decision",
        choices=[
            (Evidence.ReviewStatus.ACCEPTED, "Accept"),
            (Evidence.ReviewStatus.REJECTED, "Reject"),
        ],
        widget=forms.RadioSelect,
    )

    class Meta:
        model = Evidence
        fields = ("review_status", "reviewer_comment")
        labels = {"reviewer_comment": "Comment"}
        widgets = {"reviewer_comment": forms.Textarea(attrs={"rows": 2})}

    def clean(self):
        cleaned_data = super().clean()
        rejected = cleaned_data.get("review_status") == Evidence.ReviewStatus.REJECTED
        if rejected and not cleaned_data.get("reviewer_comment"):
            self.add_error(
                "reviewer_comment",
                forms.ValidationError(
                    "A comment is required when rejecting evidence.",
                    code="comment_required",
                ),
            )
        return cleaned_data
