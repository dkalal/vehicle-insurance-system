"""
Health monitoring and system diagnostics for Vehicle Insurance System.
Provides comprehensive health checks, metrics, and monitoring capabilities.
"""

import time
import psutil
from django.http import JsonResponse
from django.views import View
from django.db import connection
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class HealthCheckView(View):
    """
    Comprehensive health check endpoint for monitoring system status.
    """
    
    def get(self, request):
        """Return system health status."""
        start_time = time.time()
        
        health_data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': getattr(settings, 'VERSION', '1.0.0'),
            'checks': {}
        }
        
        # Database health check
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                health_data['checks']['database'] = {
                    'status': 'healthy',
                    'response_time_ms': round((time.time() - start_time) * 1000, 2)
                }
        except Exception as e:
            health_data['checks']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
        
        # Cache health check
        try:
            cache_start = time.time()
            cache.set('health_check', 'ok', 10)
            cache_value = cache.get('health_check')
            if cache_value == 'ok':
                health_data['checks']['cache'] = {
                    'status': 'healthy',
                    'response_time_ms': round((time.time() - cache_start) * 1000, 2)
                }
            else:
                raise Exception("Cache test failed")
        except Exception as e:
            health_data['checks']['cache'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
        
        # System resources check
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_percent = psutil.cpu_percent(interval=1)
            
            health_data['checks']['system'] = {
                'status': 'healthy',
                'memory_usage_percent': memory.percent,
                'disk_usage_percent': (disk.used / disk.total) * 100,
                'cpu_usage_percent': cpu_percent,
                'load_average': psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else None
            }
            
            # Mark as unhealthy if resources are critically low
            if memory.percent > 90 or (disk.used / disk.total) * 100 > 90 or cpu_percent > 90:
                health_data['checks']['system']['status'] = 'warning'
                
        except Exception as e:
            health_data['checks']['system'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # Application-specific checks
        try:
            from apps.tenants.models import Tenant
            from apps.accounts.models import User
            
            tenant_count = Tenant.objects.filter(is_active=True).count()
            user_count = User.objects.filter(is_active=True).count()
            
            health_data['checks']['application'] = {
                'status': 'healthy',
                'active_tenants': tenant_count,
                'active_users': user_count,
                'uptime_seconds': round(time.time() - start_time, 2)
            }
            
        except Exception as e:
            health_data['checks']['application'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
        
        # Overall response time
        health_data['response_time_ms'] = round((time.time() - start_time) * 1000, 2)
        
        # Set HTTP status based on health
        status_code = 200 if health_data['status'] == 'healthy' else 503
        
        return JsonResponse(health_data, status=status_code)


class MetricsView(View):
    """
    System metrics endpoint for monitoring and alerting.
    """
    
    def get(self, request):
        """Return system metrics in Prometheus format."""
        try:
            from apps.core.models import Policy, Customer, Vehicle, Payment
            from apps.tenants.models import Tenant
            
            metrics = []
            
            # Business metrics
            active_policies = Policy.objects.filter(status='active').count()
            total_customers = Customer.objects.count()
            total_vehicles = Vehicle.objects.count()
            total_tenants = Tenant.objects.filter(is_active=True).count()
            
            metrics.extend([
                f'vehicle_insurance_active_policies {active_policies}',
                f'vehicle_insurance_total_customers {total_customers}',
                f'vehicle_insurance_total_vehicles {total_vehicles}',
                f'vehicle_insurance_active_tenants {total_tenants}',
            ])
            
            # System metrics
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            cpu_percent = psutil.cpu_percent()
            
            metrics.extend([
                f'system_memory_usage_percent {memory.percent}',
                f'system_disk_usage_percent {(disk.used / disk.total) * 100:.2f}',
                f'system_cpu_usage_percent {cpu_percent}',
            ])
            
            # Database connection metrics
            db_connections = len(connection.queries) if settings.DEBUG else 0
            metrics.append(f'database_connections {db_connections}')
            
            # Cache metrics (if available)
            try:
                cache_info = cache._cache.info() if hasattr(cache._cache, 'info') else {}
                if 'hits' in cache_info and 'misses' in cache_info:
                    hit_rate = cache_info['hits'] / (cache_info['hits'] + cache_info['misses']) * 100
                    metrics.append(f'cache_hit_rate_percent {hit_rate:.2f}')
            except:
                pass
            
            response_content = '\n'.join(metrics) + '\n'
            
            return JsonResponse({
                'metrics': response_content,
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error generating metrics: {e}")
            return JsonResponse({'error': 'Failed to generate metrics'}, status=500)


class ReadinessView(View):
    """
    Kubernetes readiness probe endpoint.
    """
    
    def get(self, request):
        """Check if application is ready to serve traffic."""
        try:
            # Check database connectivity
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            
            # Check cache connectivity
            cache.set('readiness_check', 'ok', 5)
            if cache.get('readiness_check') != 'ok':
                raise Exception("Cache not ready")
            
            return JsonResponse({
                'status': 'ready',
                'timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'not_ready',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            }, status=503)


class LivenessView(View):
    """
    Kubernetes liveness probe endpoint.
    """
    
    def get(self, request):
        """Check if application is alive."""
        return JsonResponse({
            'status': 'alive',
            'timestamp': timezone.now().isoformat()
        })


def log_performance_metrics():
    """
    Log performance metrics for monitoring.
    Called periodically by Celery task.
    """
    try:
        from apps.core.models import Policy, Customer, Vehicle
        
        # Business metrics
        metrics = {
            'active_policies': Policy.objects.filter(status='active').count(),
            'total_customers': Customer.objects.count(),
            'total_vehicles': Vehicle.objects.count(),
            'policies_expiring_30_days': Policy.objects.filter(
                status='active',
                end_date__lte=timezone.now().date() + timedelta(days=30)
            ).count(),
        }
        
        # System metrics
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        metrics.update({
            'memory_usage_percent': memory.percent,
            'disk_usage_percent': (disk.used / disk.total) * 100,
            'cpu_usage_percent': psutil.cpu_percent(),
        })
        
        logger.info(f"Performance metrics: {metrics}")
        
        # Store in cache for dashboard
        cache.set('performance_metrics', metrics, 300)  # 5 minutes
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error logging performance metrics: {e}")
        return None