"""
Admin configuration for User model.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm as DjangoUserCreationForm, UserChangeForm as DjangoUserChangeForm
from simple_history.admin import SimpleHistoryAdmin
from .models import User


class CustomUserCreationForm(DjangoUserCreationForm):
    class Meta(DjangoUserCreationForm.Meta):
        model = User
        fields = (
            'username', 'email', 'is_super_admin', 'tenant', 'role', 'is_staff', 'is_active'
        )

    def clean(self):
        cleaned = super().clean()
        is_super_admin = cleaned.get('is_super_admin')
        tenant = cleaned.get('tenant')
        role = cleaned.get('role')
        if is_super_admin:
            if tenant is not None:
                self.add_error('tenant', 'Super Admin must not have a tenant.')
            if role:
                self.add_error('role', 'Super Admin must not have a role.')
        else:
            if tenant is None:
                self.add_error('tenant', 'Regular users must be assigned to a tenant.')
            if not role:
                self.add_error('role', 'Tenant users must have a role.')
        return cleaned


class CustomUserChangeForm(DjangoUserChangeForm):
    class Meta(DjangoUserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(SimpleHistoryAdmin, BaseUserAdmin):
    """
    Admin interface for User model with history tracking.
    """
    list_display = [
        'username', 'email', 'get_full_name', 'tenant', 'role', 
        'is_super_admin', 'is_active', 'created_at'
    ]
    list_filter = [
        'is_super_admin', 'is_active', 'is_staff', 'role', 'tenant', 'created_at'
    ]
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering = ['-created_at']
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    
    # Add custom fields to the default UserAdmin fieldsets
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Tenant Information', {
            'fields': ('tenant', 'is_super_admin', 'role')
        }),
        ('Additional Information', {
            'fields': ('phone_number',)
        }),
        ('Important Dates', {
            'fields': ('created_at', 'updated_at', 'last_login_at'),
            'classes': ('collapse',),
        }),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'password1', 'password2',
                'is_super_admin', 'tenant', 'role', 'is_staff', 'is_active'
            ),
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at', 'last_login_at']
    
    def get_queryset(self, request):
        """
        Customize queryset based on user permissions.
        """
        qs = super().get_queryset(request)
        
        # Super Admin sees all users
        if request.user.is_super_admin or request.user.is_superuser:
            return qs
        
        # Tenant Admin sees only their tenant's users
        if request.user.tenant:
            return qs.filter(tenant=request.user.tenant)
        
        # No access
        return qs.none()

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if 'tenant' in form.base_fields and not (request.user.is_super_admin or request.user.is_superuser):
            if request.user.tenant:
                form.base_fields['tenant'].queryset = form.base_fields['tenant'].queryset.filter(id=request.user.tenant_id)
        return form
    
    def save_model(self, request, obj, form, change):
        """
        Override save to track who modified the user.
        """
        if change:
            obj.updated_by = request.user
        super().save_model(request, obj, form, change)
    
    actions = ['activate_users', 'deactivate_users']
    
    def activate_users(self, request, queryset):
        """Activate selected users."""
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} user(s) activated.')
    activate_users.short_description = 'Activate selected users'
    
    def deactivate_users(self, request, queryset):
        """Deactivate selected users."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} user(s) deactivated.')
    deactivate_users.short_description = 'Deactivate selected users'
