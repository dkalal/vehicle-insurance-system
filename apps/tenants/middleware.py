"""
Tenant middleware for multi-tenancy support.

This middleware extracts the tenant from the request and sets it in thread-local storage,
ensuring all database queries are automatically scoped to the current tenant.
"""

from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin
from .models import Tenant
from .context import set_current_tenant, clear_current_tenant


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware to set the current tenant based on the authenticated user.
    
    **How it works:**
    1. Checks if user is authenticated
    2. If user has a tenant, sets it in thread-local storage
    3. If user is Super Admin (no tenant), allows access without tenant context
    4. Ensures tenant context is cleared after request
    
    **Security:** 
    - Non-authenticated users get no tenant context
    - Super Admin users (tenant=NULL) are allowed special access
    - Regular users MUST have a valid, active tenant
    """
    
    def process_request(self, request):
        """
        Process incoming request and set tenant context.
        """
        # Clear any existing tenant context (belt and suspenders)
        clear_current_tenant()
        
        # Allow Django admin and authentication endpoints to pass through
        path = request.path or ''
        if path.startswith('/admin/') or path == '/admin':
            return None
        if path.startswith('/accounts/login') or path.startswith('/accounts/logout'):
            return None
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            # No tenant for anonymous users
            return None
        
        # Super Admin check: is_super_admin=True and tenant=NULL
        if hasattr(request.user, 'is_super_admin') and request.user.is_super_admin:
            # Super Admin has no tenant context
            # They access different views that don't require tenant
            return None
        
        # Allow Django superusers (developer/admin) to access admin without tenant
        if getattr(request.user, 'is_superuser', False) and (path.startswith('/admin/') or path == '/admin'):
            return None
        
        # Regular tenant users must have a tenant
        if not hasattr(request.user, 'tenant') or not request.user.tenant:
            return HttpResponseForbidden(
                "User must be assigned to a tenant. Please contact your administrator."
            )
        
        tenant = request.user.tenant
        
        # Check if tenant is active
        if not tenant.is_active or tenant.is_deleted:
            return HttpResponseForbidden(
                "Your organization's account is not active. Please contact support."
            )
        
        # Set tenant in thread-local storage
        set_current_tenant(tenant)
        
        # Attach tenant to request for easy access in views
        request.tenant = tenant
        
        return None
    
    def process_response(self, request, response):
        """
        Clean up tenant context after request is processed.
        """
        clear_current_tenant()
        return response
    
    def process_exception(self, request, exception):
        """
        Clean up tenant context even if an exception occurred.
        """
        clear_current_tenant()
        return None
