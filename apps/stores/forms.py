from django import forms

from apps.accounts.models import User

from .models import Store


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = ("name", "address", "owner")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Server-side defense: restrict the owner choices to
        # owner-role users. limit_choices_to on the model is admin-only
        # cosmetic; this queryset filter rejects any posted PK that is
        # not an owner-role user with ModelChoiceField's invalid_choice.
        self.fields["owner"].queryset = User.objects.filter(role=User.Role.OWNER)
        self.fields["owner"].empty_label = "Choose an owner…"
