"""
Celery configuration for Vehicle Insurance Information System.
"""

import os
from celery import Celery

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')

# Create Celery application
app = Celery('vehicle_insurance')

# Load config from Django settings with 'CELERY_' namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    Debug task to test Celery setup.
    """
    print(f'Request: {self.request!r}')
