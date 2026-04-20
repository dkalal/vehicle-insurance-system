from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction, models
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, FormView
from django.db.models import Q
from django.utils.dateparse import parse_date

from auditlog.models import LogEntry

from apps.accounts.permissions import SuperAdminRequiredMixin
from apps.tenants.models import Tenant
from .forms import TenantAdminForm, TenantForm, PlatformConfigForm
from apps.core.models import SupportRequest
from apps.tenants import services as tenant_services
from .models import PlatformConfig
from apps.accounts.services import password_reset_service
from . import services as super_admin_services

import logging


logger = logging.getLogger(__name__)


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

    def form_invalid(self, form):
        logger.warning("Tenant create form invalid: %s", form.errors.as_json())
        messages.error(
            self.request,
            "Tenant was not saved. Please review the highlighted fields below.",
        )
        return super().form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        data = form.cleaned_data.copy()
        admin_username = data.pop("admin_username", "")
        admin_email = data.pop("admin_email", "")
        admin_password = data.pop("admin_password", "")

        self.object = tenant_services.create_tenant(**data)
        admin_user = create_or_update_tenant_admin(
            tenant=self.object,
            username=admin_username,
            email=admin_email,
            password=admin_password,
        )
        messages.success(self.request, f"Tenant '{self.object.name}' created")
        if admin_user:
            messages.success(
                self.request,
                f"Admin '{admin_user.username}' is ready for '{self.object.name}'",
            )
        return redirect(self.success_url)


class TenantUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Tenant
    form_class = TenantForm
    template_name = 'super_admin/tenant_form.html'
    success_url = reverse_lazy('super_admin:tenants')

    def form_invalid(self, form):
        logger.warning("Tenant update form invalid: %s", form.errors.as_json())
        messages.error(
            self.request,
            "Tenant was not saved. Please review the highlighted fields below.",
        )
        return super().form_invalid(form)

    @transaction.atomic
    def form_valid(self, form):
        data = form.cleaned_data.copy()
        data.pop("admin_username", None)
        data.pop("admin_email", None)
        data.pop("admin_password", None)

        tenant = form.instance
        self.object = tenant_services.update_tenant(tenant=tenant, **data)
        messages.success(self.request, f"Tenant '{self.object.name}' updated")
        return redirect(self.success_url)


def get_primary_tenant_admin(tenant):
    User = get_user_model()
    return (
        User.objects.filter(
            tenant=tenant,
            role=User.ROLE_ADMIN,
            is_super_admin=False,
        )
        .order_by("username")
        .first()
    )


def create_or_update_tenant_admin(*, tenant, username, email, password, is_active=True):
    username = (username or "").strip()
    if not username:
        return None

    User = get_user_model()
    user = get_primary_tenant_admin(tenant) or User(username=username)
    user.username = username
    user.email = (email or "").strip()
    user.tenant = tenant
    user.role = User.ROLE_ADMIN
    user.is_super_admin = False
    user.is_staff = False
    user.is_superuser = False
    user.is_active = bool(is_active)
    user.must_change_password = False
    if password:
        user.set_password(password)
    user.save()
    return user


class TenantAdminManageView(SuperAdminRequiredMixin, FormView):
    form_class = TenantAdminForm
    template_name = "super_admin/tenant_admin_form.html"
    success_url = reverse_lazy("super_admin:tenants")

    def form_invalid(self, form):
        logger.warning(
            "Tenant admin form invalid for tenant %s: %s",
            getattr(self, "tenant", None),
            form.errors.as_json(),
        )
        messages.error(
            self.request,
            "Admin was not saved. Please review the highlighted fields below.",
        )
        return super().form_invalid(form)

    def dispatch(self, request, *args, **kwargs):
        self.tenant = get_object_or_404(Tenant, pk=kwargs.get("pk"))
        self.admin_user = get_primary_tenant_admin(self.tenant)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        if not self.admin_user:
            return {"is_active": True}
        return {
            "username": self.admin_user.username,
            "email": self.admin_user.email,
            "is_active": self.admin_user.is_active,
        }

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = self.tenant
        kwargs["admin_user"] = self.admin_user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["tenant"] = self.tenant
        ctx["admin_user"] = self.admin_user
        return ctx

    @transaction.atomic
    def form_valid(self, form):
        admin_user = create_or_update_tenant_admin(
            tenant=self.tenant,
            username=form.cleaned_data["username"],
            email=form.cleaned_data.get("email", ""),
            password=form.cleaned_data.get("password", ""),
            is_active=form.cleaned_data.get("is_active", True),
        )
        messages.success(
            self.request,
            f"Admin '{admin_user.username}' is ready for '{self.tenant.name}'",
        )
        return redirect(self.success_url)


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
