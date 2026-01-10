from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from rest_framework.permissions import BasePermission


def super_admin_required(view_func):
    decorated = login_required(user_passes_test(lambda u: getattr(u, "is_super_admin", False))(view_func))
    return decorated


def tenant_user_required(view_func):
    def check(u):
        return u.is_authenticated and not getattr(u, "is_super_admin", False) and getattr(u, "tenant_id", None) is not None and getattr(getattr(u, "tenant", None), "is_active", False)
    decorated = login_required(user_passes_test(check)(view_func))
    return decorated


def tenant_role_required(*roles):
    def decorator(view_func):
        def check(u):
            if not u.is_authenticated:
                return False
            if getattr(u, "is_super_admin", False):
                return False
            if getattr(u, "tenant_id", None) is None:
                return False
            return getattr(u, "role", None) in roles
        return login_required(user_passes_test(check)(view_func))
    return decorator


class SuperAdminRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return getattr(self.request.user, "is_super_admin", False)


class TenantUserRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        u = self.request.user
        return u.is_authenticated and not getattr(u, "is_super_admin", False) and getattr(u, "tenant_id", None) is not None and getattr(getattr(u, "tenant", None), "is_active", False)


class TenantRoleRequiredMixin(TenantUserRequiredMixin):
    allowed_roles = ()

    def test_func(self):
        if not super().test_func():
            return False
        return getattr(self.request.user, "role", None) in self.allowed_roles


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_super_admin", False))


class IsTenantUser(BasePermission):
    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and not getattr(u, "is_super_admin", False) and getattr(u, "tenant_id", None) is not None and getattr(getattr(u, "tenant", None), "is_active", False))


class IsTenantAdmin(IsTenantUser):
    def has_permission(self, request, view):
        return bool(super().has_permission(request, view) and getattr(request.user, "role", None) == "admin")


class IsTenantManager(IsTenantUser):
    def has_permission(self, request, view):
        return bool(super().has_permission(request, view) and getattr(request.user, "role", None) == "manager")


class IsTenantAgent(IsTenantUser):
    def has_permission(self, request, view):
        return bool(super().has_permission(request, view) and getattr(request.user, "role", None) == "agent")
