from django.urls import path
from .views import (
    SuperAdminHomeView,
    TenantListView,
    TenantCreateView,
    TenantUpdateView,
    TenantActivateView,
    TenantDeactivateView,
    TenantSoftDeleteView,
    AuditLogListView,
    PlatformConfigUpdateView,
    SupportRequestListView,
    SupportRequestUpdateView,
    SuperAdminUserPasswordResetView,
)

app_name = "super_admin"

urlpatterns = [
    path("", SuperAdminHomeView.as_view(), name="home"),
    path("tenants/", TenantListView.as_view(), name="tenants"),
    path("tenants/new/", TenantCreateView.as_view(), name="tenant_create"),
    path("tenants/<int:pk>/edit/", TenantUpdateView.as_view(), name="tenant_update"),
    path("tenants/<int:pk>/activate/", TenantActivateView.as_view(), name="tenant_activate"),
    path("tenants/<int:pk>/deactivate/", TenantDeactivateView.as_view(), name="tenant_deactivate"),
    path("tenants/<int:pk>/soft-delete/", TenantSoftDeleteView.as_view(), name="tenant_soft_delete"),
    path("audit-logs/", AuditLogListView.as_view(), name="audit_logs"),
    path("platform-config/", PlatformConfigUpdateView.as_view(), name="platform_config"),
    path("support/", SupportRequestListView.as_view(), name="support_list"),
    path("support/<int:pk>/edit/", SupportRequestUpdateView.as_view(), name="support_update"),
    path("users/<int:user_pk>/force-reset-password/", SuperAdminUserPasswordResetView.as_view(), name="user_force_reset_password"),
]
