from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from .models import User


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(
            attrs={
                "placeholder": "Enter username",
                "autofocus": True,
                "class": "form-control",
                "autocomplete": "username",
            }
        )
    )
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "placeholder": "Enter password",
                "class": "form-control",
                "autocomplete": "current-password",
            }
        )
    )


class StyledUserMixin:
    def _style_fields(self):
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "form-check")
            else:
                field.widget.attrs.setdefault("class", "form-control")


class UserCreateForm(StyledUserMixin, UserCreationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields["avatar"].widget.attrs["accept"] = "image/png,image/jpeg,image/webp"

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "avatar",
        )


class UserUpdateForm(StyledUserMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields["avatar"].widget.attrs["accept"] = "image/png,image/jpeg,image/webp"

    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "avatar",
            "is_active",
        )


class ProfileForm(StyledUserMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
        self.fields["avatar"].widget.attrs["accept"] = "image/png,image/jpeg,image/webp"

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "avatar")
