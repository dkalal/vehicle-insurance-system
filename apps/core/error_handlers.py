"""
Advanced error handling for Vehicle Insurance System.
Provides user-friendly error pages and comprehensive error logging.
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import requires_csrf_token
from django.views.decorators.cache import never_cache
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@never_cache
@requires_csrf_token
def handler404(request, exception=None):
    """Custom 404 error handler."""
    logger.warning(f"404 error for path: {request.path} from IP: {request.META.get('REMOTE_ADDR')}")
    
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Resource not found',
            'status_code': 404,
            'path': request.path
        }, status=404)
    
    context = {
        'error_code': '404',
        'error_title': 'Page Not Found',
        'error_message': 'The page you are looking for does not exist.',
        'show_home_link': True,
    }
    
    return render(request, 'errors/error.html', context, status=404)


@never_cache
@requires_csrf_token
def handler500(request):
    """Custom 500 error handler."""
    logger.error(f"500 error for path: {request.path} from IP: {request.META.get('REMOTE_ADDR')}")
    
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Internal server error',
            'status_code': 500,
            'message': 'An unexpected error occurred. Please try again later.'
        }, status=500)
    
    context = {
        'error_code': '500',
        'error_title': 'Server Error',
        'error_message': 'An unexpected error occurred. Our team has been notified.',
        'show_home_link': True,
    }
    
    return render(request, 'errors/error.html', context, status=500)


@never_cache
@requires_csrf_token
def handler403(request, exception=None):
    """Custom 403 error handler."""
    logger.warning(f"403 error for path: {request.path} from IP: {request.META.get('REMOTE_ADDR')}")
    
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'Access forbidden',
            'status_code': 403,
            'message': 'You do not have permission to access this resource.'
        }, status=403)
    
    context = {
        'error_code': '403',
        'error_title': 'Access Forbidden',
        'error_message': 'You do not have permission to access this resource.',
        'show_home_link': True,
    }
    
    return render(request, 'errors/error.html', context, status=403)


def csrf_failure(request, reason=""):
    """Custom CSRF failure handler."""
    logger.warning(f"CSRF failure for path: {request.path} from IP: {request.META.get('REMOTE_ADDR')} - Reason: {reason}")
    
    if request.path.startswith('/api/'):
        return JsonResponse({
            'error': 'CSRF verification failed',
            'status_code': 403,
            'message': 'CSRF token missing or incorrect. Please refresh the page and try again.'
        }, status=403)
    
    context = {
        'error_code': '403',
        'error_title': 'Security Error',
        'error_message': 'Security verification failed. Please refresh the page and try again.',
        'show_home_link': True,
    }
    
    return render(request, 'errors/error.html', context, status=403)