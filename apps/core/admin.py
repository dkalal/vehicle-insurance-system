from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline

from apps.core.models.customer import Customer
from apps.core.models.vehicle import Vehicle
from apps.core.models.policy import Policy
from apps.core.models.payment import Payment
from apps.dynamic_fields.models import FieldValue


class FieldValueInline(GenericTabularInline):
    model = FieldValue
    extra = 0
    ct_field = 'content_type'
    ct_fk_field = 'object_id'
    fields = ('definition', 'text_value', 'number_value', 'date_value', 'bool_value', 'option_value')


class BlockSuperAdminAdminMixin:
    """Disallow Super Admin from tenant business operations in admin."""
    def _allow(self, request):
        return not getattr(request.user, 'is_super_admin', False)

    def has_view_permission(self, request, obj=None):
        return self._allow(request) and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return self._allow(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._allow(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._allow(request) and super().has_delete_permission(request, obj)


class FieldValueTenantMixin:
    """Ensure inline FieldValue rows inherit the parent's tenant automatically."""
    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        parent = form.instance
        for obj in instances:
            if isinstance(obj, FieldValue):
                obj.tenant = getattr(parent, 'tenant', None)
            obj.save()
        # Handle deletions and m2m
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()


@admin.register(Customer)
class CustomerAdmin(BlockSuperAdminAdminMixin, FieldValueTenantMixin, admin.ModelAdmin):
    list_display = ('id', 'customer_type', 'email', 'phone', 'tenant', 'created_at', 'is_active')
    list_filter = ('tenant', 'customer_type', 'deleted_at', 'created_at')
    search_fields = ('email', 'phone', 'first_name', 'last_name', 'company_name', 'registration_number', 'tax_id')
    autocomplete_fields = ('created_by', 'updated_by', 'tenant')
    inlines = [FieldValueInline]
    def is_active(self, obj):
        return obj.deleted_at is None
    is_active.boolean = True


@admin.register(Vehicle)
class VehicleAdmin(BlockSuperAdminAdminMixin, FieldValueTenantMixin, admin.ModelAdmin):
    list_display = ('id', 'registration_number', 'owner', 'tenant', 'vehicle_type', 'make', 'model', 'year', 'is_active')
    list_filter = ('tenant', 'vehicle_type', 'deleted_at', 'year', 'created_at')
    search_fields = ('registration_number', 'make', 'model', 'chassis_number', 'engine_number')
    autocomplete_fields = ('owner', 'created_by', 'updated_by', 'tenant')
    inlines = [FieldValueInline]
    def is_active(self, obj):
        return obj.deleted_at is None
    is_active.boolean = True


@admin.register(Policy)
class PolicyAdmin(BlockSuperAdminAdminMixin, FieldValueTenantMixin, admin.ModelAdmin):
    list_display = ('id', 'policy_number', 'vehicle', 'tenant', 'status', 'start_date', 'end_date', 'premium_amount')
    list_filter = ('tenant', 'status', 'start_date', 'end_date', 'created_at')
    search_fields = ('policy_number', 'vehicle__registration_number', 'notes')
    autocomplete_fields = ('vehicle', 'created_by', 'updated_by', 'tenant')
    inlines = [FieldValueInline]


@admin.register(Payment)
class PaymentAdmin(BlockSuperAdminAdminMixin, admin.ModelAdmin):
    list_display = ('id', 'policy', 'tenant', 'amount', 'is_verified', 'payment_method', 'payment_date')
    list_filter = ('tenant', 'is_verified', 'payment_method', 'payment_date', 'created_at')
    search_fields = ('policy__policy_number', 'reference_number', 'payer_name', 'notes')
    autocomplete_fields = ('policy', 'verified_by', 'created_by', 'updated_by', 'tenant')
