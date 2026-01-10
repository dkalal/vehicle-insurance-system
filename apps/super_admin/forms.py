from django import forms
from apps.tenants.models import Tenant
from .models import PlatformConfig


class TenantForm(forms.ModelForm):
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
