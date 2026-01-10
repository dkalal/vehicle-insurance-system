"""
Settings package initialization.
Loads development settings by default.
Override by setting DJANGO_SETTINGS_MODULE environment variable.
"""

import os

# Default to development settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
