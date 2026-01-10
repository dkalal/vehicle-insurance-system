"""
Admin configuration for Tenant model.
"""

from django.contrib import admin
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    """
    Admin interface for Tenant model.
    """
    list_display = ['name', 'slug', 'is_active', 'contact_email', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'slug', 'contact_email', 'domain']
    readonly_fields = ['created_at', 'updated_at', 'deleted_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'domain')
        }),
        ('Contact', {
            'fields': ('contact_email', 'contact_phone')
        }),
        ('Status', {
            'fields': ('is_active', 'deleted_at')
        }),
        ('Configuration', {
            'fields': ('settings',),
            'classes': ('collapse',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
    
    def get_queryset(self, request):
        """Include soft-deleted tenants in admin."""
        return super().get_queryset(request).all()
    
    actions = ['activate_tenants', 'deactivate_tenants']
    
    def activate_tenants(self, request, queryset):
        """Activate selected tenants."""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} tenant(s) activated.')
    activate_tenants.short_description = 'Activate selected tenants'
    
    def deactivate_tenants(self, request, queryset):
        """Deactivate selected tenants."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} tenant(s) deactivated.')
    deactivate_tenants.short_description = 'Deactivate selected tenants'
