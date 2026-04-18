"""
Monitoring URLs configuration.
"""

from django.urls import path
from .views import HealthCheckView, DetailedHealthView, MetricsView, ReadinessView, LivenessView

app_name = 'monitoring'

urlpatterns = [
    path('', HealthCheckView.as_view(), name='health'),
    path('live/', LivenessView.as_view(), name='liveness'),
    path('ready/', ReadinessView.as_view(), name='readiness'),
    path('detailed/', DetailedHealthView.as_view(), name='detailed'),
    path('metrics/', MetricsView.as_view(), name='metrics'),
]