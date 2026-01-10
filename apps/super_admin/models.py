from django.db import models
from simple_history.models import HistoricalRecords
from auditlog.registry import auditlog


class PlatformConfig(models.Model):
    maintenance_mode = models.BooleanField(default=False, db_index=True)
    support_email = models.EmailField(blank=True)
    announcement_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    history = HistoricalRecords()

    class Meta:
        verbose_name = "Platform Configuration"
        verbose_name_plural = "Platform Configuration"

    def __str__(self):
        return "Platform Configuration"

    @classmethod
    def get_solo(cls):
        obj = cls.objects.first()
        if not obj:
            obj = cls.objects.create()
        return obj


auditlog.register(PlatformConfig)

# Create your models here.
