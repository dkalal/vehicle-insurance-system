from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.core.paginator import Paginator
import json

from apps.accounts.permissions import TenantUserRequiredMixin
from .services import NotificationService
from .models import Notification, TenantNotificationSettings, UserNotificationPreference


@method_decorator([login_required], name='dispatch')
class NotificationListAPIView(TenantUserRequiredMixin, View):
    """API endpoint for fetching user notifications."""
    
    def get(self, request):
        page = int(request.GET.get('page', 1))
        per_page = min(int(request.GET.get('per_page', 20)), 50)  # Max 50 per page
        unread_only = request.GET.get('unread_only', '').lower() == 'true'
        notification_type = request.GET.get('type')
        types_param = request.GET.getlist('types')
        priority = request.GET.get('priority')

        types = None
        if types_param:
            types = types_param
        elif notification_type:
            types = [notification_type]
        
        notifications = NotificationService.get_user_notifications(
            tenant=request.tenant,
            user=request.user,
            limit=per_page * 5,  # Get more for pagination
            unread_only=unread_only,
            types=types,
            priority=priority,
        )
        
        paginator = Paginator(notifications, per_page)
        page_obj = paginator.get_page(page)
        
        data = {
            'notifications': [
                {
                    'id': str(n.id),
                    'type': n.type,
                    'priority': n.priority,
                    'title': n.title,
                    'message': n.message,
                    'is_read': n.is_read,
                    'created_at': n.created_at.isoformat(),
                    'action_url': n.action_url,
                    'action_text': n.action_text,
                }
                for n in page_obj
            ],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginator.count,
                'pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            },
            'unread_count': NotificationService.get_unread_count(
                tenant=request.tenant,
                user=request.user
            )
        }
        
        return JsonResponse(data)


@method_decorator([login_required, csrf_exempt], name='dispatch')
class NotificationMarkReadAPIView(TenantUserRequiredMixin, View):
    """API endpoint for marking notifications as read."""
    
    def post(self, request, notification_id=None):
        if notification_id:
            # Mark single notification as read
            try:
                notification = Notification.objects.get(
                    id=notification_id,
                    tenant=request.tenant,
                    user=request.user
                )
                notification.mark_as_read()
                return JsonResponse({'success': True})
            except Notification.DoesNotExist:
                return JsonResponse({'error': 'Notification not found'}, status=404)
        else:
            # Mark all notifications as read
            count = NotificationService.mark_all_as_read(
                tenant=request.tenant,
                user=request.user
            )
            return JsonResponse({'success': True, 'marked_count': count})


@method_decorator([login_required], name='dispatch')
class NotificationCountAPIView(TenantUserRequiredMixin, View):
    """API endpoint for getting unread notification count."""
    
    def get(self, request):
        count = NotificationService.get_unread_count(
            tenant=request.tenant,
            user=request.user
        )
        return JsonResponse({'unread_count': count})


@method_decorator([login_required, csrf_exempt], name='dispatch')
class NotificationPreferencesAPIView(TenantUserRequiredMixin, View):
    """API endpoint for getting and updating user notification preferences."""

    def get(self, request):
        tenant = request.tenant
        user = request.user

        tenant_settings = TenantNotificationSettings.objects.filter(
            tenant=tenant,
            deleted_at__isnull=True,
        ).first()
        if not tenant_settings:
            tenant_settings = TenantNotificationSettings.objects.create(tenant=tenant)

        user_pref = UserNotificationPreference.objects.filter(
            tenant=tenant,
            user=user,
            deleted_at__isnull=True,
        ).first()

        data = {
            'tenant_defaults': {
                'policy_expiry_enabled': bool(tenant_settings.policy_expiry_enabled),
                'payment_notifications_enabled': bool(tenant_settings.payment_notifications_enabled),
                'compliance_alerts_enabled': bool(tenant_settings.compliance_alerts_enabled),
                'system_notifications_enabled': bool(tenant_settings.system_notifications_enabled),
            },
            'user_preferences': None,
        }

        if user_pref:
            data['user_preferences'] = {
                'policy_expiry_enabled': user_pref.policy_expiry_enabled,
                'payment_notifications_enabled': user_pref.payment_notifications_enabled,
                'compliance_alerts_enabled': user_pref.compliance_alerts_enabled,
                'system_notifications_enabled': user_pref.system_notifications_enabled,
            }

        return JsonResponse(data)

    def post(self, request):
        tenant = request.tenant
        user = request.user

        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except (TypeError, ValueError):
            return JsonResponse({'error': 'Invalid JSON payload'}, status=400)

        user_pref, _ = UserNotificationPreference.objects.get_or_create(
            tenant=tenant,
            user=user,
            defaults={},
        )

        fields = [
            'policy_expiry_enabled',
            'payment_notifications_enabled',
            'compliance_alerts_enabled',
            'system_notifications_enabled',
        ]

        updated_fields = []
        for field in fields:
            if field in payload:
                setattr(user_pref, field, payload[field])
                updated_fields.append(field)

        if updated_fields:
            user_pref.save(update_fields=updated_fields + ['updated_at'])

        return JsonResponse({'success': True})


@method_decorator([login_required], name='dispatch')
class NotificationCenterView(TenantUserRequiredMixin, TemplateView):
    template_name = 'notifications_center.html'