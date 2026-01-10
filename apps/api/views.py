"""
RESTful API for Vehicle Insurance System.
Provides comprehensive API endpoints with proper authentication, permissions, and serialization.
"""

from rest_framework import serializers, viewsets, permissions, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta

from apps.core.models import Customer, Vehicle, Policy, Payment
from apps.tenants.context import get_current_tenant


class TenantAwarePagination(PageNumberPagination):
    """Custom pagination with tenant-aware page sizes."""
    page_size = 25
    page_size_query_param = 'page_size'
    max_page_size = 100


class TenantPermission(permissions.BasePermission):
    """Permission class ensuring tenant isolation."""
    
    def has_permission(self, request, view):
        return (request.user.is_authenticated and 
                hasattr(request.user, 'tenant') and 
                request.user.tenant and 
                request.user.tenant.is_active)
    
    def has_object_permission(self, request, view, obj):
        return (hasattr(obj, 'tenant') and 
                obj.tenant == request.user.tenant)


# Serializers
class CustomerSerializer(serializers.ModelSerializer):
    """Serializer for Customer model with validation."""
    
    full_name = serializers.SerializerMethodField()
    vehicle_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Customer
        fields = [
            'id', 'customer_type', 'first_name', 'last_name', 'full_name',
            'email', 'phone_number', 'address', 'date_of_birth',
            'vehicle_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'full_name', 'vehicle_count']
    
    def get_full_name(self, obj):
        return obj.get_full_name()
    
    def get_vehicle_count(self, obj):
        return obj.vehicles.active().count()
    
    def validate_email(self, value):
        """Ensure email uniqueness within tenant."""
        tenant = get_current_tenant()
        if tenant:
            existing = Customer.objects.for_tenant(tenant).filter(email=value)
            if self.instance:
                existing = existing.exclude(pk=self.instance.pk)
            if existing.exists():
                raise serializers.ValidationError("Email already exists for this tenant.")
        return value


class VehicleSerializer(serializers.ModelSerializer):
    """Serializer for Vehicle model."""
    
    owner_name = serializers.CharField(source='owner.get_full_name', read_only=True)
    active_policy = serializers.SerializerMethodField()
    
    class Meta:
        model = Vehicle
        fields = [
            'id', 'owner', 'owner_name', 'vehicle_type', 'make', 'model',
            'year', 'registration_number', 'vin', 'color', 'active_policy',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'owner_name', 'active_policy']
    
    def get_active_policy(self, obj):
        active_policy = obj.policies.filter(status='active').first()
        if active_policy:
            return {
                'id': active_policy.id,
                'policy_number': active_policy.policy_number,
                'end_date': active_policy.end_date
            }
        return None


class PolicySerializer(serializers.ModelSerializer):
    """Serializer for Policy model."""
    
    vehicle_info = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()
    total_paid = serializers.SerializerMethodField()
    
    class Meta:
        model = Policy
        fields = [
            'id', 'policy_number', 'vehicle', 'vehicle_info', 'start_date',
            'end_date', 'premium_amount', 'coverage_amount', 'status',
            'policy_type', 'payment_status', 'total_paid', 'created_at'
        ]
        read_only_fields = ['id', 'policy_number', 'created_at', 'vehicle_info', 'payment_status', 'total_paid']
    
    def get_vehicle_info(self, obj):
        return {
            'registration_number': obj.vehicle.registration_number,
            'make': obj.vehicle.make,
            'model': obj.vehicle.model,
            'owner_name': obj.vehicle.owner.get_full_name()
        }
    
    def get_payment_status(self, obj):
        return 'Fully Paid' if obj.is_fully_paid() else 'Pending Payment'
    
    def get_total_paid(self, obj):
        return str(obj.get_total_paid())


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""
    
    policy_number = serializers.CharField(source='policy.policy_number', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'policy', 'policy_number', 'amount', 'payment_date',
            'payment_method', 'reference_number', 'is_verified',
            'notes', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'policy_number']


# ViewSets
class CustomerViewSet(viewsets.ModelViewSet):
    """ViewSet for Customer management."""
    
    serializer_class = CustomerSerializer
    permission_classes = [TenantPermission]
    pagination_class = TenantAwarePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['customer_type']
    search_fields = ['first_name', 'last_name', 'email', 'phone_number']
    ordering_fields = ['first_name', 'last_name', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        tenant = get_current_tenant()
        return Customer.objects.for_tenant(tenant).with_audit_info()
    
    @action(detail=True, methods=['get'])
    def vehicles(self, request, pk=None):
        """Get all vehicles for a customer."""
        customer = self.get_object()
        vehicles = customer.vehicles.active().select_related('owner')
        serializer = VehicleSerializer(vehicles, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get customer statistics."""
        tenant = get_current_tenant()
        queryset = Customer.objects.for_tenant(tenant)
        
        stats = {
            'total_customers': queryset.count(),
            'individual_customers': queryset.filter(customer_type='individual').count(),
            'corporate_customers': queryset.filter(customer_type='corporate').count(),
            'recent_customers': queryset.recent(30).count(),
        }
        return Response(stats)


class VehicleViewSet(viewsets.ModelViewSet):
    """ViewSet for Vehicle management."""
    
    serializer_class = VehicleSerializer
    permission_classes = [TenantPermission]
    pagination_class = TenantAwarePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['vehicle_type', 'make', 'owner']
    search_fields = ['registration_number', 'make', 'model', 'vin']
    ordering_fields = ['registration_number', 'make', 'model', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        tenant = get_current_tenant()
        return Vehicle.objects.for_tenant(tenant).select_related('owner')
    
    @action(detail=True, methods=['get'])
    def policies(self, request, pk=None):
        """Get all policies for a vehicle."""
        vehicle = self.get_object()
        policies = vehicle.policies.active().order_by('-created_at')
        serializer = PolicySerializer(policies, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def uninsured(self, request):
        """Get vehicles without active policies."""
        tenant = get_current_tenant()
        vehicles = Vehicle.objects.for_tenant(tenant).uninsured()
        serializer = self.get_serializer(vehicles, many=True)
        return Response(serializer.data)


class PolicyViewSet(viewsets.ModelViewSet):
    """ViewSet for Policy management."""
    
    serializer_class = PolicySerializer
    permission_classes = [TenantPermission]
    pagination_class = TenantAwarePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'policy_type', 'vehicle']
    search_fields = ['policy_number', 'vehicle__registration_number']
    ordering_fields = ['policy_number', 'start_date', 'end_date', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        tenant = get_current_tenant()
        return Policy.objects.for_tenant(tenant).select_related('vehicle', 'vehicle__owner')
    
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Activate a policy."""
        policy = self.get_object()
        try:
            policy.activate()
            return Response({'status': 'Policy activated successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)}, 
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel a policy."""
        policy = self.get_object()
        reason = request.data.get('reason', '')
        policy.cancel(reason)
        return Response({'status': 'Policy cancelled successfully'})
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """Get policies expiring within 30 days."""
        tenant = get_current_tenant()
        policies = Policy.objects.for_tenant(tenant).expiring_soon(30)
        serializer = self.get_serializer(policies, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def revenue_summary(self, request):
        """Get revenue summary."""
        tenant = get_current_tenant()
        summary = Policy.objects.revenue_summary(tenant)
        return Response(summary)


class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for Payment management."""
    
    serializer_class = PaymentSerializer
    permission_classes = [TenantPermission]
    pagination_class = TenantAwarePagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['payment_method', 'is_verified', 'policy']
    search_fields = ['reference_number', 'policy__policy_number']
    ordering_fields = ['payment_date', 'amount', 'created_at']
    ordering = ['-payment_date']
    
    def get_queryset(self):
        tenant = get_current_tenant()
        return Payment.objects.for_tenant(tenant).select_related('policy', 'policy__vehicle')
    
    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify a payment."""
        payment = self.get_object()
        payment.is_verified = True
        payment.save(update_fields=['is_verified', 'updated_at'])
        
        # Check if policy can be activated after this payment
        if payment.policy.is_fully_paid():
            can_activate, reason = payment.policy.can_activate()
            if can_activate:
                payment.policy.activate()
                return Response({
                    'status': 'Payment verified and policy activated',
                    'policy_activated': True
                })
        
        return Response({
            'status': 'Payment verified',
            'policy_activated': False
        })
    
    @action(detail=False, methods=['get'])
    def pending_verification(self, request):
        """Get payments pending verification."""
        tenant = get_current_tenant()
        payments = Payment.objects.for_tenant(tenant).pending_verification()
        serializer = self.get_serializer(payments, many=True)
        return Response(serializer.data)