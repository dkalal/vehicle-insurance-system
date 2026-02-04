from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from apps.core.models.vehicle import Vehicle
from apps.core.models.vehicle_record import LATRARecord, VehiclePermit


class VehicleComplianceService:
    STATUS_COMPLIANT = 'compliant'
    STATUS_AT_RISK = 'at_risk'
    STATUS_NON_COMPLIANT = 'non_compliant'

    @staticmethod
    def get_active_insurance(*, vehicle: Vehicle):
        if vehicle is None:
            raise ValidationError({'vehicle': 'Vehicle is required'})
        return vehicle.get_active_policy()

    @staticmethod
    def get_active_latra(*, vehicle: Vehicle):
        if vehicle is None:
            raise ValidationError({'vehicle': 'Vehicle is required'})
        return (
            LATRARecord.objects
            .filter(vehicle=vehicle, status=LATRARecord.STATUS_ACTIVE)
            .order_by('-start_date')
            .first()
        )

    @staticmethod
    def get_active_permits(*, vehicle: Vehicle):
        if vehicle is None:
            raise ValidationError({'vehicle': 'Vehicle is required'})
        return (
            VehiclePermit.objects
            .select_related('permit_type')
            .filter(vehicle=vehicle, status=VehiclePermit.STATUS_ACTIVE)
            .order_by('-start_date')
        )

    @staticmethod
    def get_compliance_snapshot(*, vehicle: Vehicle):
        if vehicle is None:
            raise ValidationError({'vehicle': 'Vehicle is required'})
        active_insurance = VehicleComplianceService.get_active_insurance(vehicle=vehicle)
        active_latra = VehicleComplianceService.get_active_latra(vehicle=vehicle)
        active_permits = list(VehicleComplianceService.get_active_permits(vehicle=vehicle))
        return {
            'vehicle': vehicle,
            'active_insurance': active_insurance,
            'active_latra': active_latra,
            'active_permits': active_permits,
        }

    @staticmethod
    def compute_compliance_status(*, vehicle: Vehicle, risk_window_days: int = 30):
        """
        Compute real-time compliance status for a vehicle.
        
        Args:
            vehicle: Vehicle instance
            risk_window_days: Days before expiry to consider 'at risk'
            
        Returns:
            dict with status, reasons, and expiring_items
        """
        if vehicle is None:
            raise ValidationError({'vehicle': 'Vehicle is required'})
        
        today = timezone.now().date()
        risk_threshold = today + timedelta(days=risk_window_days)
        
        issues = []
        expiring_soon = []
        
        # Check insurance
        insurance = VehicleComplianceService.get_active_insurance(vehicle=vehicle)
        if not insurance:
            issues.append('No active insurance')
        elif insurance.end_date <= today:
            issues.append('Insurance expired')
        elif insurance.end_date <= risk_threshold:
            expiring_soon.append(f'Insurance expires {insurance.end_date}')
        
        # Check LATRA
        latra = VehicleComplianceService.get_active_latra(vehicle=vehicle)
        if latra:
            if latra.end_date and latra.end_date <= today:
                issues.append('LATRA expired')
            elif latra.end_date and latra.end_date <= risk_threshold:
                expiring_soon.append(f'LATRA expires {latra.end_date}')
        
        # Determine status
        if issues:
            status = VehicleComplianceService.STATUS_NON_COMPLIANT
        elif expiring_soon:
            status = VehicleComplianceService.STATUS_AT_RISK
        else:
            status = VehicleComplianceService.STATUS_COMPLIANT
        
        return {
            'status': status,
            'issues': issues,
            'expiring_soon': expiring_soon,
            'insurance': insurance,
            'latra': latra,
        }

    @staticmethod
    def get_tenant_compliance_summary(*, tenant, risk_window_days: int = 30):
        """
        Get compliance summary for all vehicles in a tenant.
        
        Args:
            tenant: Tenant instance
            risk_window_days: Days before expiry to consider 'at risk'
            
        Returns:
            dict with counts by status
        """
        from apps.core.models.vehicle import Vehicle
        
        vehicles = Vehicle.objects.filter(tenant=tenant, deleted_at__isnull=True)
        
        compliant = 0
        at_risk = 0
        non_compliant = 0
        
        for vehicle in vehicles:
            result = VehicleComplianceService.compute_compliance_status(
                vehicle=vehicle,
                risk_window_days=risk_window_days
            )
            if result['status'] == VehicleComplianceService.STATUS_COMPLIANT:
                compliant += 1
            elif result['status'] == VehicleComplianceService.STATUS_AT_RISK:
                at_risk += 1
            else:
                non_compliant += 1
        
        return {
            'total': vehicles.count(),
            'compliant': compliant,
            'at_risk': at_risk,
            'non_compliant': non_compliant,
        }
