"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect

urlpatterns = [
    # Admin interface
    path('admin/', admin.site.urls),
    
    # Authentication
    path('accounts/', include(('apps.accounts.urls', 'accounts'), namespace='accounts')),
    
    # Main application
    path('dashboard/', include(('apps.core.urls', 'dashboard'), namespace='dashboard')),
    
    # Super Admin
    path('super-admin/', include(('apps.super_admin.urls', 'super_admin'), namespace='super_admin')),
    
    # API endpoints
    path('api/', include('apps.api.urls')),
    
    # Health monitoring
    path('health/', include('apps.monitoring.urls')),
    
    # Root redirect
    path('', lambda request: redirect('accounts:login')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Debug toolbar
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns = [
            path('__debug__/', include(debug_toolbar.urls)),
        ] + urlpatterns

# Custom error handlers
handler404 = 'apps.core.error_handlers.handler404'
handler500 = 'apps.core.error_handlers.handler500'
handler403 = 'apps.core.error_handlers.handler403'
