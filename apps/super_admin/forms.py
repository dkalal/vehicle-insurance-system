from django import forms
from django.contrib.auth import get_user_model
from django.utils.text import slugify

from apps.tenants.models import Tenant
from .models import PlatformConfig


class TenantForm(forms.ModelForm):
    admin_username = forms.CharField(
        max_length=150,
        required=False,
        help_text="Optional: create or update the first admin for this organization.",
    )
    admin_email = forms.EmailField(required=False)
    admin_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Optional for new organizations. Required if you are creating a new admin.",
    )

    class Meta:
        model = Tenant
        fields = [
            'name',
            'slug',
            'domain',
            'contact_email',
            'contact_phone',
            'is_active',
            'settings',
        ]
        widgets = {
            'settings': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["domain"].required = False
        self.fields["settings"].required = False
        self.fields["settings"].initial = self.fields["settings"].initial or {}
        self.fields["settings"].help_text = (
            "Optional JSON settings. Leave blank to use default settings."
        )

    def clean_slug(self):
        slug = (self.cleaned_data.get('slug') or '').strip().lower()
        if slug:
            return slug
        return slugify(self.cleaned_data.get("name") or "")

    def clean_domain(self):
        return (self.cleaned_data.get("domain") or "").strip() or None

    def clean_settings(self):
        settings = self.cleaned_data.get("settings")
        return settings or {}

    def clean(self):
        cleaned = super().clean()
        username = (cleaned.get("admin_username") or "").strip()
        email = (cleaned.get("admin_email") or "").strip()
        password = cleaned.get("admin_password") or ""

        if password and not username:
            self.add_error(
                "admin_username",
                "Enter an admin username when setting an admin password.",
            )

        if username and not self.instance.pk and not password:
            self.add_error(
                "admin_password",
                "Enter an initial password for the first organization admin.",
            )

        if username:
            User = get_user_model()
            if User.objects.filter(username=username).exists():
                self.add_error(
                    "admin_username",
                    "A user with this username already exists. Choose a unique admin username.",
                )

        if email:
            User = get_user_model()
            if User.objects.filter(email=email).exists():
                self.add_error(
                    "admin_email",
                    "A user with this email already exists. Use a different admin email.",
                )

        return cleaned


class TenantAdminForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(render_value=True),
        help_text="Required for a new admin. Leave blank to keep the current password.",
    )
    is_active = forms.BooleanField(required=False, initial=True)

    def __init__(self, *args, tenant=None, admin_user=None, **kwargs):
        self.tenant = tenant
        self.admin_user = admin_user
        super().__init__(*args, **kwargs)
        if admin_user:
            self.fields["password"].help_text = (
                "Leave blank to keep this admin's current password."
            )

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        User = get_user_model()
        existing = User.objects.filter(username=username).first()
        if existing and existing != self.admin_user:
            raise forms.ValidationError(
                "A user with this username already exists. Choose a unique username."
            )
        return username

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        if not email:
            return email
        User = get_user_model()
        existing = User.objects.filter(email=email).first()
        if existing and existing != self.admin_user:
            raise forms.ValidationError(
                "A user with this email already exists. Use a different email."
            )
        return email

    def clean(self):
        cleaned = super().clean()
        if not self.admin_user and not cleaned.get("password"):
            self.add_error(
                "password",
                "Enter an initial password for this organization admin.",
            )
        return cleaned


class PlatformConfigForm(forms.ModelForm):
    class Meta:
        model = PlatformConfig
        fields = [
            'maintenance_mode',
            'support_email',
            'announcement_message',
        ]
        widgets = {
            'announcement_message': forms.Textarea(attrs={'rows': 4}),
        }
