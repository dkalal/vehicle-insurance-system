from django.db import models
from django.utils import timezone

from .base import BaseModel


class TenantOnboardingState(BaseModel):
    STATUS_NOT_STARTED = 'not_started'
    STATUS_WELCOME_SHOWN = 'welcome_shown'
    STATUS_COMPANY_SETUP = 'company_setup'
    STATUS_VEHICLE_BASICS = 'vehicle_basics'
    STATUS_VEHICLE_OWNER = 'vehicle_owner'
    STATUS_VEHICLE_DOCUMENTS = 'vehicle_documents'
    STATUS_COMPLETED = 'completed'

    STATUS_CHOICES = [
        (STATUS_NOT_STARTED, 'Not started'),
        (STATUS_WELCOME_SHOWN, 'Welcome shown'),
        (STATUS_COMPANY_SETUP, 'Company setup'),
        (STATUS_VEHICLE_BASICS, 'Vehicle basics'),
        (STATUS_VEHICLE_OWNER, 'Vehicle ownership'),
        (STATUS_VEHICLE_DOCUMENTS, 'Vehicle documents'),
        (STATUS_COMPLETED, 'Completed'),
    ]

    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_NOT_STARTED,
        db_index=True,
    )
    current_step = models.CharField(max_length=32, blank=True, default='')
    first_vehicle = models.ForeignKey(
        'Vehicle',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='onboarding_first_for',
    )
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Tenant onboarding state'
        verbose_name_plural = 'Tenant onboarding states'
        indexes = [
            models.Index(fields=['tenant', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['tenant'],
                condition=models.Q(deleted_at__isnull=True),
                name='unique_onboarding_state_per_tenant',
            ),
        ]

    def mark_completed(self):
        self.status = self.STATUS_COMPLETED
        self.current_step = ''
        self.completed_at = timezone.now()
