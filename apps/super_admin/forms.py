from django import forms
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

    def clean_slug(self):
        slug = self.cleaned_data.get('slug')
        return (slug or '').lower()

    def clean(self):
        cleaned = super().clean()
        username = (cleaned.get("admin_username") or "").strip()
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
