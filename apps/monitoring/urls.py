"""
Monitoring URLs configuration.
"""

from django.urls import path
from .views import HealthCheckView, MetricsView, ReadinessView, LivenessView

app_name = 'monitoring'

urlpatterns = [
    path('', HealthCheckView.as_view(), name='health'),
    path('metrics/', MetricsView.as_view(), name='metrics'),
    path('ready/', ReadinessView.as_view(), name='readiness'),
    path('live/', LivenessView.as_view(), name='liveness'),
]