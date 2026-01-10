"""
Advanced tenant-aware managers with performance optimizations.
Implements efficient querying, caching, and tenant isolation.
"""

from django.db import models
from django.core.cache import cache
from django.db.models import Q, Prefetch
from typing import Optional, Any, Dict
import logging

logger = logging.getLogger(__name__)


class TenantAwareQuerySet(models.QuerySet):
    """
    QuerySet with tenant-aware filtering and performance optimizations.
    """
    
    def for_tenant(self, tenant):
        """Filter queryset for specific tenant with caching."""
        if not tenant:
            return self.none()
        
        cache_key = f"tenant_{tenant.id}_queryset_{self.model._meta.label_lower}"
        cached_pks = cache.get(cache_key)
        
        if cached_pks is not None:
            return self.filter(pk__in=cached_pks)
        
        queryset = self.filter(tenant=tenant, deleted_at__isnull=True)
        
        # Cache primary keys for 5 minutes
        pks = list(queryset.values_list('pk', flat=True)[:1000])  # Limit cache size
        cache.set(cache_key, pks, 300)
        
        return queryset
    
    def active(self):
        """Filter for non-deleted records."""
        return self.filter(deleted_at__isnull=True)
    
    def deleted(self):
        """Filter for soft-deleted records."""
        return self.filter(deleted_at__isnull=False)
    
    def with_audit_info(self):
        """Optimize queries by selecting related audit fields."""
        return self.select_related('created_by', 'updated_by')
    
    def recent(self, days=30):
        """Filter for recently created records."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff)


class TenantAwareManager(models.Manager):
    """
    Manager that automatically filters by tenant and provides performance optimizations.
    """
    
    def get_queryset(self):
        """Return tenant-aware queryset."""
        return TenantAwareQuerySet(self.model, using=self._db)
    
    def for_tenant(self, tenant):
        """Get records for specific tenant."""
        return self.get_queryset().for_tenant(tenant)
    
    def active(self):
        """Get active (non-deleted) records."""
        return self.get_queryset().active()
    
    def create_for_tenant(self, tenant, **kwargs):
        """Create record with tenant automatically set."""
        kwargs['tenant'] = tenant
        return self.create(**kwargs)
    
    def bulk_create_for_tenant(self, tenant, objs, **kwargs):
        """Bulk create records with tenant set."""
        for obj in objs:
            obj.tenant = tenant
        return self.bulk_create(objs, **kwargs)


class TenantAwareSoftDeleteManager(TenantAwareManager):
    """
    Manager combining tenant awareness with soft delete functionality.
    """
    
    def get_queryset(self):
        """Return queryset excluding soft-deleted records by default."""
        return super().get_queryset().active()
    
    def all_with_deleted(self):
        """Get all records including soft-deleted ones."""
        return TenantAwareQuerySet(self.model, using=self._db)
    
    def deleted_only(self):
        """Get only soft-deleted records."""
        return self.all_with_deleted().deleted()
    
    def hard_delete(self, **kwargs):
        """Permanently delete records (use with extreme caution)."""
        logger.warning(f"Hard delete requested for {self.model._meta.label}: {kwargs}")
        return super().get_queryset().filter(**kwargs).delete()


class PolicyManager(TenantAwareSoftDeleteManager):
    """
    Specialized manager for Policy model with business logic optimizations.
    """
    
    def active_policies(self):
        """Get active policies with optimized queries."""
        return (self.get_queryset()
                .filter(status='active')
                .select_related('vehicle', 'vehicle__owner', 'tenant')
                .prefetch_related('payments'))
    
    def expiring_soon(self, days=30):
        """Get policies expiring within specified days."""
        from django.utils import timezone
        from datetime import timedelta, date
        
        cutoff_date = date.today() + timedelta(days=days)
        return (self.active_policies()
                .filter(end_date__lte=cutoff_date)
                .order_by('end_date'))
    
    def for_vehicle(self, vehicle):
        """Get all policies for a specific vehicle."""
        return (self.get_queryset()
                .filter(vehicle=vehicle)
                .order_by('-created_at'))
    
    def revenue_summary(self, tenant, start_date=None, end_date=None):
        """Get revenue summary for tenant."""
        from django.db.models import Sum, Count
        
        queryset = self.for_tenant(tenant).filter(status='active')
        
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(start_date__lte=end_date)
        
        return queryset.aggregate(
            total_premium=Sum('premium_amount'),
            policy_count=Count('id')
        )


class CustomerManager(TenantAwareSoftDeleteManager):
    """
    Specialized manager for Customer model.
    """
    
    def with_policies(self):
        """Get customers with their policies prefetched."""
        return (self.get_queryset()
                .prefetch_related(
                    Prefetch('vehicles__policies', 
                            queryset=self.model._meta.get_field('vehicles').related_model.objects.active())
                ))
    
    def search(self, query):
        """Search customers by name, email, or phone."""
        if not query:
            return self.none()
        
        return self.get_queryset().filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone_number__icontains=query)
        )


class VehicleManager(TenantAwareSoftDeleteManager):
    """
    Specialized manager for Vehicle model.
    """
    
    def with_active_policy(self):
        """Get vehicles with their active policy."""
        return (self.get_queryset()
                .select_related('owner')
                .prefetch_related(
                    Prefetch('policies',
                            queryset=self.model._meta.get_field('policies').related_model.objects.filter(status='active'))
                ))
    
    def uninsured(self):
        """Get vehicles without active policies."""
        from apps.core.models.policy import Policy
        active_policy_vehicle_ids = Policy.objects.active_policies().values_list('vehicle_id', flat=True)
        return self.get_queryset().exclude(id__in=active_policy_vehicle_ids)


class PaymentManager(TenantAwareSoftDeleteManager):
    """
    Specialized manager for Payment model.
    """
    
    def verified(self):
        """Get verified payments only."""
        return self.get_queryset().filter(is_verified=True)
    
    def pending_verification(self):
        """Get payments pending verification."""
        return self.get_queryset().filter(is_verified=False)
    
    def for_policy(self, policy):
        """Get all payments for a specific policy."""
        return (self.get_queryset()
                .filter(policy=policy)
                .order_by('-payment_date'))
    
    def revenue_by_period(self, tenant, start_date, end_date):
        """Calculate revenue for a specific period."""
        from django.db.models import Sum
        
        return (self.for_tenant(tenant)
                .verified()
                .filter(payment_date__range=[start_date, end_date])
                .aggregate(total=Sum('amount'))['total'] or 0)


# Cache utilities for managers
class ManagerCacheUtils:
    """Utilities for manager-level caching."""
    
    @staticmethod
    def get_cache_key(model_name: str, tenant_id: int, suffix: str = '') -> str:
        """Generate consistent cache keys."""
        return f"manager_{model_name}_{tenant_id}_{suffix}"
    
    @staticmethod
    def invalidate_tenant_cache(tenant_id: int, model_name: str = None):
        """Invalidate all cache entries for a tenant."""
        if model_name:
            pattern = f"manager_{model_name}_{tenant_id}_*"
        else:
            pattern = f"manager_*_{tenant_id}_*"
        
        # Note: This is a simplified version. In production, use Redis pattern deletion
        logger.info(f"Cache invalidation requested for pattern: {pattern}")