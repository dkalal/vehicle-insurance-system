"""
Thread-local storage for current tenant context.

This module provides thread-safe storage and retrieval of the current tenant
throughout the request-response cycle.
"""

import threading
from typing import Optional
from .models import Tenant

# Thread-local storage for tenant context
_thread_locals = threading.local()


def get_current_tenant() -> Optional[Tenant]:
    """
    Get the current tenant from thread-local storage.
    
    Returns:
        Current Tenant instance or None if not set.
        
    Usage:
        >>> from apps.tenants.context import get_current_tenant
        >>> tenant = get_current_tenant()
        >>> if tenant:
        >>>     print(f"Current tenant: {tenant.name}")
    """
    return getattr(_thread_locals, 'tenant', None)


def set_current_tenant(tenant: Optional[Tenant]) -> None:
    """
    Set the current tenant in thread-local storage.
    
    Args:
        tenant: Tenant instance to set as current, or None to clear.
        
    Usage:
        >>> from apps.tenants.context import set_current_tenant
        >>> set_current_tenant(my_tenant)
    """
    _thread_locals.tenant = tenant


def clear_current_tenant() -> None:
    """
    Clear the current tenant from thread-local storage.
    
    Usage:
        >>> from apps.tenants.context import clear_current_tenant
        >>> clear_current_tenant()
    """
    if hasattr(_thread_locals, 'tenant'):
        del _thread_locals.tenant
