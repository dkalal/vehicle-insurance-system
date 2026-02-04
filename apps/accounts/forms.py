from django import forms
from django.contrib.auth import password_validation

from apps.core.models.vehicle import Vehicle
from apps.accounts.models import User


class StaffVehicleTypeForm(forms.Form):
    vehicle_types = forms.MultipleChoiceField(
        choices=Vehicle.VEHICLE_TYPE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle_types'].help_text = (
            "Select the vehicle types this staff member can manage. "
            "Leave blank to allow all types."
        )


class StaffCreateForm(forms.Form):
    """Form for tenant admins to create staff users.

    This is intentionally a plain Form (not ModelForm) so that model-level
    tenant validation happens in the service layer, not inside the form.
    """

    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    phone_number = forms.CharField(max_length=20, required=False)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)
    is_active = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Simple Tailwind-style classes for dashboard consistency
        base = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' ' if existing else '') + base

    def clean_role(self):
        role = self.cleaned_data.get('role')
        valid_roles = {User.ROLE_ADMIN, User.ROLE_MANAGER, User.ROLE_AGENT}
        if role not in valid_roles:
            raise forms.ValidationError('Invalid role for tenant staff user.')
        return role


class ForcePasswordChangeForm(forms.Form):
    new_password1 = forms.CharField(widget=forms.PasswordInput)
    new_password2 = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        base = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' ' if existing else '') + base

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('new_password1')
        p2 = cleaned.get('new_password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('The two password fields did not match.')
        if p1 and self.user is not None:
            password_validation.validate_password(p1, self.user)
        return cleaned


class UserPasswordChangeForm(forms.Form):
    old_password = forms.CharField(widget=forms.PasswordInput)
    new_password1 = forms.CharField(widget=forms.PasswordInput)
    new_password2 = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        base = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' ' if existing else '') + base

    def clean(self):
        cleaned = super().clean()
        user = self.user
        old = cleaned.get('old_password')
        p1 = cleaned.get('new_password1')
        p2 = cleaned.get('new_password2')

        if user is not None and old:
            if not user.check_password(old):
                self.add_error('old_password', 'Your current password was entered incorrectly.')

        if p1 and p2 and p1 != p2:
            raise forms.ValidationError('The two new password fields did not match.')

        if p1 and user is not None:
            password_validation.validate_password(p1, user)

        return cleaned


class ProfileUpdateForm(forms.Form):
    """Simple profile form for the currently logged-in user.

    Intentionally a plain Form so that business rules and tenant safety
    remain in the service layer instead of being hidden inside ModelForms.
    """

    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)
    phone_number = forms.CharField(max_length=20, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' ' if existing else '') + base

