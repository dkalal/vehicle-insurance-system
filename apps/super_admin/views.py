from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction, models
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView, ListView, CreateView, UpdateView
from django.db.models import Q
from django.utils.dateparse import parse_date

from auditlog.models import LogEntry

from apps.accounts.permissions import SuperAdminRequiredMixin
from apps.tenants.models import Tenant
from .forms import TenantForm, PlatformConfigForm
from apps.core.models import SupportRequest
from apps.tenants import services as tenant_services
from .models import PlatformConfig
from apps.accounts.services import password_reset_service
from . import services as super_admin_services


class SuperAdminHomeView(SuperAdminRequiredMixin, TemplateView):
    template_name = 'super_admin/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["overview"] = super_admin_services.get_platform_overview()
        return ctx


class TenantListView(SuperAdminRequiredMixin, ListView):
    model = Tenant
    template_name = 'super_admin/tenants_list.html'
    context_object_name = 'tenants'
    paginate_by = 25

    def get_queryset(self):
        qs = Tenant.objects.all().order_by('name')
        q = (self.request.GET.get('q') or '').strip()
        status = (self.request.GET.get('status') or '').strip()
        if q:
            qs = qs.filter(models.Q(name__icontains=q) | models.Q(slug__icontains=q) | models.Q(domain__icontains=q))
        if status == 'active':
            qs = qs.filter(is_active=True, deleted_at__isnull=True)
        elif status == 'inactive':
            qs = qs.filter(is_active=False, deleted_at__isnull=True)
        elif status == 'deleted':
            qs = qs.filter(deleted_at__isnull=False)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()
        return ctx


class TenantCreateView(SuperAdminRequiredMixin, CreateView):
    model = Tenant
    form_class = TenantForm
    template_name = 'super_admin/tenant_form.html'
    success_url = reverse_lazy('super_admin:tenants')

    @transaction.atomic
    def form_valid(self, form):
        tenant = tenant_services.create_tenant(**form.cleaned_data)
        messages.success(self.request, f"Tenant '{tenant.name}' created")
        return redirect(self.get_success_url())


class TenantUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Tenant
    form_class = TenantForm
    template_name = 'super_admin/tenant_form.html'
    success_url = reverse_lazy('super_admin:tenants')

    @transaction.atomic
    def form_valid(self, form):
        tenant = form.instance
        tenant_services.update_tenant(tenant=tenant, **form.cleaned_data)
        messages.success(self.request, f"Tenant '{tenant.name}' updated")
        return redirect(self.get_success_url())


class TenantActivateView(SuperAdminRequiredMixin, View):
    def post(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        tenant_services.activate_tenant(tenant)
        messages.success(request, f"Tenant '{tenant.name}' activated")
        return redirect(reverse_lazy('super_admin:tenants'))


class TenantDeactivateView(SuperAdminRequiredMixin, View):
    def post(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        tenant_services.deactivate_tenant(tenant)
        messages.info(request, f"Tenant '{tenant.name}' deactivated")
        return redirect(reverse_lazy('super_admin:tenants'))


class TenantSoftDeleteView(SuperAdminRequiredMixin, View):
    def post(self, request, pk):
        tenant = get_object_or_404(Tenant, pk=pk)
        tenant_services.soft_delete_tenant(tenant)
        messages.warning(request, f"Tenant '{tenant.name}' soft-deleted")
        return redirect(reverse_lazy('super_admin:tenants'))


class AuditLogListView(SuperAdminRequiredMixin, ListView):
    template_name = 'super_admin/audit_logs.html'
    context_object_name = 'logs'
    paginate_by = 50

    def get_queryset(self):
        qs = LogEntry.objects.all().select_related('actor', 'content_type')

        # Filters
        q = (self.request.GET.get('q') or '').strip()
        model = (self.request.GET.get('model') or '').strip()
        user = (self.request.GET.get('user') or '').strip()
        action = (self.request.GET.get('action') or '').strip().lower()
        date_from = parse_date((self.request.GET.get('date_from') or '').strip())
        date_to = parse_date((self.request.GET.get('date_to') or '').strip())

        if q:
            qs = qs.filter(
                Q(object_repr__icontains=q)
                | Q(object_pk__icontains=q)
                | Q(changes__icontains=q)
                | Q(additional_data__icontains=q)
            )

        if model:
            qs = qs.filter(content_type__model__icontains=model)

        if user:
            if user.isdigit():
                qs = qs.filter(actor_id=int(user))
            else:
                qs = qs.filter(Q(actor__username__icontains=user) | Q(actor__email__icontains=user))

        action_map = {'create': 0, 'update': 1, 'delete': 2}
        if action in action_map:
            qs = qs.filter(action=action_map[action])

        if date_from:
            qs = qs.filter(timestamp__date__gte=date_from)
        if date_to:
            qs = qs.filter(timestamp__date__lte=date_to)

        return qs.order_by('-timestamp')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update({
            'filters': {
                'q': self.request.GET.get('q', ''),
                'model': self.request.GET.get('model', ''),
                'user': self.request.GET.get('user', ''),
                'action': self.request.GET.get('action', ''),
                'date_from': self.request.GET.get('date_from', ''),
                'date_to': self.request.GET.get('date_to', ''),
            }
        })
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()
        return ctx


class PlatformConfigUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = PlatformConfig
    form_class = PlatformConfigForm
    template_name = 'super_admin/platform_config.html'
    success_url = reverse_lazy('super_admin:platform_config')

    def get_object(self, queryset=None):
        return PlatformConfig.get_solo()

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, "Platform configuration updated")
        return super().form_valid(form)


class SupportRequestListView(SuperAdminRequiredMixin, ListView):
    template_name = 'super_admin/support_list.html'
    context_object_name = 'tickets'
    paginate_by = 25

    def get_queryset(self):
        qs = (
            SupportRequest._base_manager
            .select_related('tenant', 'assigned_to')
            .only('subject', 'status', 'priority', 'created_at', 'tenant__name', 'assigned_to__email')
            .order_by('-created_at')
        )
        q = (self.request.GET.get('q') or '').strip()
        status = (self.request.GET.get('status') or '').strip()
        priority = (self.request.GET.get('priority') or '').strip()
        tenant = (self.request.GET.get('tenant') or '').strip()
        if q:
            qs = qs.filter(models.Q(subject__icontains=q) | models.Q(message__icontains=q))
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if tenant:
            if tenant.isdigit():
                qs = qs.filter(tenant_id=int(tenant))
            else:
                qs = qs.filter(tenant__name__icontains=tenant)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['filters'] = {
            'q': self.request.GET.get('q', ''),
            'status': self.request.GET.get('status', ''),
            'priority': self.request.GET.get('priority', ''),
            'tenant': self.request.GET.get('tenant', ''),
        }
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()
        return ctx


class SupportRequestUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = SupportRequest
    fields = ['status', 'priority', 'assigned_to', 'resolved_at']
    template_name = 'super_admin/support_update.html'
    success_url = reverse_lazy('super_admin:support_list')

    def get_queryset(self):
        return SupportRequest._base_manager.all()

    @transaction.atomic
    def form_valid(self, form):
        messages.success(self.request, 'Support request updated')
        return super().form_valid(form)


class SuperAdminUserPasswordResetView(SuperAdminRequiredMixin, View):
    """Allow Super Admin to force reset a tenant user's password across tenants."""

    def post(self, request, user_pk):
        User = get_user_model()
        target = get_object_or_404(User, pk=user_pk)
        reason = request.POST.get('reason', '')
        try:
            temp_password = password_reset_service.super_admin_force_reset_password(
                actor=request.user,
                target_user=target,
                reason=reason,
                ip_address=request.META.get('REMOTE_ADDR'),
            )
        except ValidationError as exc:
            messages.error(request, '; '.join(exc.messages))
        else:
            display_name = target.get_full_name() or target.username
            messages.success(
                request,
                f'Password reset for {display_name}. Temporary password: {temp_password}. '
                'Ask the user to change it after login.'
            )
        return redirect(reverse_lazy('super_admin:home'))
