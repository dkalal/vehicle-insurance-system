"""
Template context processor for tenant information.

Makes tenant data available in all templates.
"""

def tenant_context(request):
    """
    Add tenant information to template context.
    
    Args:
        request: Django HttpRequest object.
        
    Returns:
        Dictionary with tenant information.
    """
    context = {
        'current_tenant': None,
        'is_super_admin': False,
    }
    
    if request.user.is_authenticated:
        # Check if Super Admin
        if hasattr(request.user, 'is_super_admin'):
            context['is_super_admin'] = request.user.is_super_admin
        
        # Add tenant if available
        if hasattr(request, 'tenant'):
            context['current_tenant'] = request.tenant
    
    return context
