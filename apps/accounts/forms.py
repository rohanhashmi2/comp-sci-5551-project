from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class RegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email", "role")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].widget = forms.Select(
            choices=[("", "Choose your role…"), *User.Role.choices]
        )
        self.fields["role"].required = True


class EmailAuthenticationForm(AuthenticationForm):
    # CharField (not EmailField) so an injection pattern reaches the ORM
    # layer; parameterization is the defense verified by AC 2.5.
    username = forms.CharField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )
