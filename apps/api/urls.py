"""
API URL configuration for Vehicle Insurance System.
"""

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.documentation import include_docs_urls
from .views import CustomerViewSet, VehicleViewSet, PolicyViewSet, PaymentViewSet

app_name = 'api'

# Create router and register viewsets
router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'vehicles', VehicleViewSet, basename='vehicle')
router.register(r'policies', PolicyViewSet, basename='policy')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('v1/', include(router.urls)),
    path('docs/', include_docs_urls(title='Vehicle Insurance API')),
    path('auth/', include('rest_framework.urls')),
]