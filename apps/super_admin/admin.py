from django.contrib import admin
from .models import PlatformConfig

@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    list_display = ("maintenance_mode", "support_email", "updated_at")
    readonly_fields = ("created_at", "updated_at")
