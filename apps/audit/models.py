import uuid

from django.db import models
from django.utils import timezone


class PasswordResetAudit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey('tenants.Tenant', on_delete=models.PROTECT, related_name='password_reset_events')
    actor = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='password_resets_performed')
    target_user = models.ForeignKey('accounts.User', on_delete=models.PROTECT, related_name='password_resets_received')
    reason = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['tenant', 'created_at']),
            models.Index(fields=['tenant', 'target_user', 'created_at']),
        ]
        verbose_name = 'Password reset audit'
        verbose_name_plural = 'Password reset audits'
