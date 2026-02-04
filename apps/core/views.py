from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, View, FormView
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from django.http import HttpResponse
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.accounts.permissions import TenantUserRequiredMixin, TenantRoleRequiredMixin
from apps.dynamic_fields.models import FieldDefinition
from apps.dynamic_fields import services as df_services
from apps.tenants import services as tenant_services
from .models import Customer, Vehicle, Policy, Payment, SupportRequest, LATRARecord, VehiclePermit, PermitType
from .forms import (
    CustomerForm,
    VehicleForm,
    PolicyForm,
    PaymentForm,
    PaymentReviewForm,
    SupportRequestForm,
    LATRARecordForm,
    VehiclePermitForm,
    CompanyOnboardingForm,
    OrganizationSettingsForm,
    VehicleBasicsOnboardingForm,
    OwnerOnboardingForm,
    VehicleBulkImportForm,
    PermitTypeForm,
)
from .services import customer_service, vehicle_service, policy_service, payment_service, VehicleComplianceService
from .services import vehicle_access_service, vehicle_import_service
from .services import latra_service, permit_service, permit_type_service
from .services import onboarding_service
from apps.accounts.forms import StaffVehicleTypeForm, StaffCreateForm
from apps.accounts.services import vehicle_type_access_service, staff_service
from apps.accounts.models import UserVehicleTypeAssignment


class TenantScopedQuerysetMixin:
    """Helper mixin to safely scope querysets to the current tenant.

    Views using this mixin should still perform any domain-specific filtering
    (like vehicle access rules) on top of the tenant filter.
    """

    def filter_for_tenant(self, queryset, field_name="tenant"):
        tenant = getattr(self.request, "tenant", None)
        if tenant is None:
            # For tenant-only views, absence of tenant means no data should be returned.
            return queryset.none()
        return queryset.filter(**{field_name: tenant})


class DashboardHomeView(TenantUserRequiredMixin, TenantScopedQuerysetMixin, TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        tenant = getattr(self.request, 'tenant', None)
        
        # Get risk window from tenant settings
        risk_days = 30
        if tenant:
            try:
                risk_days = int(tenant.get_setting('expiry_reminder_days', 30))
            except Exception:
                risk_days = 30
        
        # Vehicle-centric compliance metrics
        compliance_summary = VehicleComplianceService.get_tenant_compliance_summary(
            tenant=tenant,
            risk_window_days=risk_days,
        )

        # Legacy metrics for backward compatibility (strictly tenant-scoped)
        if tenant is not None:
            active_policies = Policy.objects.filter(
                tenant=tenant,
                status=Policy.STATUS_ACTIVE,
            ).count()
            customers_count = Customer.objects.filter(tenant=tenant).count()

            # Expiring policies for quick action
            today = timezone.now().date()
            soon = today + timedelta(days=risk_days)
            expiring_list = (
                Policy.objects
                .select_related('vehicle', 'vehicle__owner')
                .filter(
                    tenant=tenant,
                    status=Policy.STATUS_ACTIVE,
                    end_date__gt=today,
                    end_date__lte=soon,
                )
                .order_by('end_date')[:5]
            )
        else:
            active_policies = 0
            customers_count = 0
            expiring_list = Policy.objects.none()

        onboarding_needed = False
        if tenant:
            onboarding_needed = onboarding_service.needs_onboarding(tenant=tenant)
        
        ctx.update({
            'compliance': compliance_summary,
            'metrics': {
                'active_policies': active_policies,
                'expiring_soon': compliance_summary['at_risk'],
                'vehicles': compliance_summary['total'],
                'customers': customers_count,
            },
            'expiring_policies': expiring_list,
            'onboarding_needed': onboarding_needed,
            'risk_window_days': risk_days,
        })
        return ctx


class OnboardingWelcomeView(TenantRoleRequiredMixin, View):
    allowed_roles = ('admin', 'manager')
    template_name = 'onboarding/welcome.html'

    def get(self, request):
        if not onboarding_service.needs_onboarding(tenant=request.tenant):
            return redirect('dashboard:home')
        return TemplateView.as_view(template_name=self.template_name)(request)

    def post(self, request):
        if not onboarding_service.needs_onboarding(tenant=request.tenant):
            return redirect('dashboard:home')
        onboarding_service.mark_welcome_shown(tenant=request.tenant, user=request.user)
        return redirect('dashboard:onboarding_company')


class OnboardingCompanyView(TenantRoleRequiredMixin, FormView):
    allowed_roles = ('admin', 'manager')
    template_name = 'onboarding/company.html'
    form_class = CompanyOnboardingForm

    def dispatch(self, request, *args, **kwargs):
        if not onboarding_service.needs_onboarding(tenant=request.tenant):
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        tenant = self.request.tenant
        return {
            'name': tenant.name,
            'contact_email': tenant.contact_email,
            'contact_phone': tenant.contact_phone,
            'operation_type': tenant.settings.get('operation_type', ''),
            'region': tenant.settings.get('default_region', ''),
            'city': tenant.settings.get('default_city', ''),
        }

    def form_valid(self, form):
        onboarding_service.update_company_context(
            tenant=self.request.tenant,
            user=self.request.user,
            name=form.cleaned_data.get('name'),
            contact_email=form.cleaned_data.get('contact_email'),
            contact_phone=form.cleaned_data.get('contact_phone'),
            operation_type=form.cleaned_data.get('operation_type'),
            region=form.cleaned_data.get('region'),
            city=form.cleaned_data.get('city'),
        )
        return redirect('dashboard:onboarding_vehicle_basics')


class OnboardingVehicleBasicsView(TenantRoleRequiredMixin, FormView):
    allowed_roles = ('admin', 'manager')
    template_name = 'onboarding/vehicle_basics.html'
    form_class = VehicleBasicsOnboardingForm

    def dispatch(self, request, *args, **kwargs):
        if not onboarding_service.needs_onboarding(tenant=request.tenant):
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return self.request.session.get('onboarding_vehicle_basics', {})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        defs = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_VEHICLE,
            is_active=True,
        ).order_by('order', 'name')
        ctx['df_defs'] = defs
        if self.request.method == 'POST':
            ctx['df_values'] = {d.key: self.request.POST.get(f"df_{d.key}") for d in defs}
        else:
            ctx['df_values'] = self.request.session.get('onboarding_vehicle_df', {})
        return ctx

    def form_valid(self, form):
        defs = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_VEHICLE,
            is_active=True,
        )
        missing = []
        for df in defs:
            raw = self.request.POST.get(f"df_{df.key}")
            if df.is_required:
                if df.data_type in ('text', 'dropdown', 'number', 'date'):
                    if not (raw and str(raw).strip()):
                        missing.append(df.name)
                elif df.data_type == 'boolean':
                    if raw not in ('true', 'false'):
                        missing.append(df.name)
        if missing:
            form.add_error(None, f"Please fill required additional fields: {', '.join(missing)}")
            return self.form_invalid(form)

        self.request.session['onboarding_vehicle_basics'] = form.cleaned_data
        self.request.session['onboarding_vehicle_df'] = {df.key: self.request.POST.get(f"df_{df.key}") for df in defs}
        onboarding_service.mark_vehicle_basics(tenant=self.request.tenant, user=self.request.user)
        return redirect('dashboard:onboarding_owner')


class OnboardingOwnerView(TenantRoleRequiredMixin, FormView):
    allowed_roles = ('admin', 'manager')
    template_name = 'onboarding/owner.html'
    form_class = OwnerOnboardingForm

    def dispatch(self, request, *args, **kwargs):
        if not onboarding_service.needs_onboarding(tenant=request.tenant):
            return redirect('dashboard:home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        defs = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_CUSTOMER,
            is_active=True,
        ).order_by('order', 'name')
        ctx['df_defs'] = defs
        if self.request.method == 'POST':
            ctx['df_values'] = {d.key: self.request.POST.get(f"df_{d.key}") for d in defs}
        else:
            ctx['df_values'] = self.request.session.get('onboarding_customer_df', {})
        return ctx

    def form_valid(self, form):
        basics = self.request.session.get('onboarding_vehicle_basics')
        if not basics:
            messages.info(self.request, 'Please enter vehicle basics first.')
            return redirect('dashboard:onboarding_vehicle_basics')

        defs = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_CUSTOMER,
            is_active=True,
        )
        missing = []
        for df in defs:
            raw = self.request.POST.get(f"df_{df.key}")
            if df.is_required:
                if df.data_type in ('text', 'dropdown', 'number', 'date'):
                    if not (raw and str(raw).strip()):
                        missing.append(df.name)
                elif df.data_type == 'boolean':
                    if raw not in ('true', 'false'):
                        missing.append(df.name)
        if missing:
            form.add_error(None, f"Please fill required additional fields: {', '.join(missing)}")
            return self.form_invalid(form)

        try:
            owner = customer_service.create_customer(
                created_by=self.request.user,
                customer_type=form.cleaned_data['customer_type'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data['phone'],
                first_name=form.cleaned_data.get('first_name', ''),
                last_name=form.cleaned_data.get('last_name', ''),
                company_name=form.cleaned_data.get('company_name', ''),
            )
            vehicle = vehicle_service.create_vehicle(
                created_by=self.request.user,
                owner=owner,
                vehicle_type=basics['vehicle_type'],
                registration_number=basics['registration_number'],
                make=basics['make'],
                model=basics['model'],
                year=basics['year'],
                color=basics.get('color') or '',
            )
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError):
                if isinstance(e.message_dict, dict):
                    for field, errs in e.message_dict.items():
                        for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    form.add_error(None, str(e))
                return self.form_invalid(form)
            raise
        customer_values = {df.key: self.request.POST.get(f"df_{df.key}") for df in defs}
        df_services.bulk_set_by_keys(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_CUSTOMER,
            obj=owner,
            values=customer_values,
        )
        vehicle_defs = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_VEHICLE,
            is_active=True,
        )
        vehicle_values = self.request.session.get('onboarding_vehicle_df', {})
        df_services.bulk_set_by_keys(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_VEHICLE,
            obj=vehicle,
            values=vehicle_values,
        )
        onboarding_service.mark_vehicle_owner(tenant=self.request.tenant, user=self.request.user, vehicle=vehicle)
        self.request.session['onboarding_vehicle_id'] = vehicle.pk
        self.request.session.pop('onboarding_vehicle_basics', None)
        self.request.session.pop('onboarding_vehicle_df', None)
        self.request.session['onboarding_customer_df'] = customer_values
        return redirect('dashboard:onboarding_documents')


class OnboardingDocumentsView(TenantRoleRequiredMixin, View):
    allowed_roles = ('admin', 'manager')
    template_name = 'onboarding/documents.html'

    def get(self, request):
        if not onboarding_service.needs_onboarding(tenant=request.tenant):
            return redirect('dashboard:home')
        vehicle_id = request.session.get('onboarding_vehicle_id')
        vehicle = None
        if vehicle_id:
            vehicle = get_object_or_404(Vehicle, pk=vehicle_id)
        ctx = {
            'vehicle': vehicle,
            'latra_url': vehicle and reverse_lazy('dashboard:vehicles_latra_create', kwargs={'vehicle_pk': vehicle.pk}),
            'permit_url': vehicle and reverse_lazy('dashboard:vehicles_permit_create', kwargs={'vehicle_pk': vehicle.pk}),
        }
        return TemplateView.as_view(template_name=self.template_name, extra_context=ctx)(request)

    def post(self, request):
        if not onboarding_service.needs_onboarding(tenant=request.tenant):
            return redirect('dashboard:home')
        onboarding_service.mark_vehicle_documents(tenant=request.tenant, user=request.user)
        onboarding_service.mark_completed(tenant=request.tenant, user=request.user)
        return redirect('dashboard:onboarding_success')


class OnboardingSuccessView(TenantRoleRequiredMixin, TemplateView):
    allowed_roles = ('admin', 'manager')
    template_name = 'onboarding/success.html'

    def dispatch(self, request, *args, **kwargs):
        if onboarding_service.needs_onboarding(tenant=request.tenant):
            return redirect('dashboard:onboarding_welcome')
        return super().dispatch(request, *args, **kwargs)


class OrganizationSettingsView(TenantRoleRequiredMixin, FormView):
    allowed_roles = ('admin',)
    template_name = 'dashboard/organization_settings.html'
    form_class = OrganizationSettingsForm
    success_url = reverse_lazy('dashboard:organization_settings')

    def get_initial(self):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            return {}
        return {
            'name': tenant.name,
            'contact_email': tenant.contact_email,
            'contact_phone': tenant.contact_phone,
            'operation_type': tenant.settings.get('operation_type', ''),
            'region': tenant.settings.get('default_region', ''),
            'city': tenant.settings.get('default_city', ''),
            'expiry_reminder_days': tenant.get_setting('expiry_reminder_days', 30),
        }

    def form_valid(self, form):
        tenant = getattr(self.request, 'tenant', None)
        if not tenant:
            form.add_error(None, 'Tenant context is required to update organization settings.')
            return self.form_invalid(form)

        data = form.cleaned_data
        try:
            tenant_services.update_tenant_settings_for_admin(
                tenant=tenant,
                name=data.get('name', tenant.name),
                contact_email=data.get('contact_email', tenant.contact_email),
                contact_phone=data.get('contact_phone', tenant.contact_phone),
                operation_type=data.get('operation_type'),
                region=data.get('region'),
                city=data.get('city'),
                expiry_reminder_days=data.get('expiry_reminder_days'),
            )
        except ValidationError as e:
            # Mirror the error handling pattern used elsewhere in this module
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError) and isinstance(getattr(e, 'message_dict', None), dict):
                for field, errs in e.message_dict.items():
                    for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                        form.add_error(field if field in form.fields else None, msg)
            else:
                form.add_error(None, str(e))
            return self.form_invalid(form)

        messages.success(self.request, 'Organization settings have been updated.')
        return super().form_valid(form)


class PolicyDetailView(TenantRoleRequiredMixin, TenantScopedQuerysetMixin, DetailView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Policy
    template_name = 'dashboard/policies_detail.html'
    context_object_name = 'policy'

    def get_queryset(self):
        qs = (
            Policy.objects
            .select_related('vehicle', 'vehicle__owner')
            .prefetch_related('payments')
        )
        qs = self.filter_for_tenant(qs)
        allowed = vehicle_access_service.get_allowed_vehicle_types_for_user(self.request.user)
        if allowed:
            qs = qs.filter(vehicle__vehicle_type__in=allowed)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        defs = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_POLICY,
            is_active=True,
        ).order_by('order', 'name')
        values = {}
        obj = ctx.get('policy')
        if obj:
            for d in defs:
                try:
                    values[d.key] = df_services.get_field_value(definition=d, obj=obj)
                except Exception:
                    values[d.key] = None
            # Expose payment/activation insight for the UI so admins can
            # understand why a policy is or is not active.
            try:
                total_paid = obj.get_total_paid()
            except Exception:
                total_paid = None
            ctx['total_paid'] = total_paid
            can_activate, reason = obj.can_activate()
            ctx['can_activate'] = can_activate
            ctx['activation_block_reason'] = None if can_activate else reason
        ctx['df_defs'] = defs
        ctx['df_values'] = values
        return ctx


class PolicyUpdateView(TenantRoleRequiredMixin, TenantScopedQuerysetMixin, UpdateView):
    allowed_roles = ('admin', 'manager')
    model = Policy
    form_class = PolicyForm
    template_name = 'dashboard/policies_form.html'
    success_url = reverse_lazy('dashboard:policies_list')

    def get_queryset(self):
        qs = Policy.objects.select_related('vehicle', 'vehicle__owner')
        qs = self.filter_for_tenant(qs)
        allowed = vehicle_access_service.get_allowed_vehicle_types_for_user(self.request.user)
        if allowed:
            qs = qs.filter(vehicle__vehicle_type__in=allowed)
        return qs

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['df_defs'] = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_POLICY,
            is_active=True,
        ).order_by('order', 'name')
        if self.request.method == 'POST':
            ctx['df_values'] = {d.key: self.request.POST.get(f"df_{d.key}") for d in ctx['df_defs']}
        else:
            obj = getattr(self, 'object', None) or ctx.get('object')
            if obj:
                values = {}
                for d in ctx['df_defs']:
                    try:
                        values[d.key] = df_services.get_field_value(definition=d, obj=obj)
                    except Exception:
                        values[d.key] = None
                ctx['df_values'] = values
            else:
                ctx['df_values'] = {}
        return ctx


class LATRARecordCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = LATRARecordForm
    template_name = 'dashboard/latra_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.vehicle = get_object_or_404(Vehicle, pk=kwargs.get('vehicle_pk'), tenant=request.tenant)
        vehicle_access_service.ensure_user_can_access_vehicle(user=request.user, vehicle=self.vehicle)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['vehicle'] = self.vehicle
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault('start_date', timezone.now().date())
        return initial

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            record = latra_service.create_latra_record(
                created_by=self.request.user,
                vehicle=self.vehicle,
                latra_number=d['latra_number'],
                license_type=d['license_type'],
                start_date=d['start_date'],
                end_date=d.get('end_date'),
                route=d.get('route', ''),
            )
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError):
                if isinstance(e.message_dict, dict):
                    for field, errs in e.message_dict.items():
                        for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    form.add_error(None, str(e))
                return self.form_invalid(form)
            raise
        self.object = record
        messages.success(self.request, 'LATRA record created successfully')
        return redirect('dashboard:vehicles_detail', pk=self.vehicle.pk)


class VehiclePermitCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = VehiclePermitForm
    template_name = 'dashboard/permits_form.html'

    def dispatch(self, request, *args, **kwargs):
        self.vehicle = get_object_or_404(Vehicle, pk=kwargs.get('vehicle_pk'), tenant=request.tenant)
        vehicle_access_service.ensure_user_can_access_vehicle(user=request.user, vehicle=self.vehicle)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['vehicle'] = self.vehicle
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = getattr(self.vehicle, 'tenant', None)
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        initial.setdefault('start_date', timezone.now().date())
        return initial

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            permit = permit_service.create_vehicle_permit(
                created_by=self.request.user,
                vehicle=self.vehicle,
                permit_type=d['permit_type'],
                reference_number=d['reference_number'],
                start_date=d['start_date'],
                end_date=d.get('end_date'),
                document=d.get('document'),
            )
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError):
                if isinstance(e.message_dict, dict):
                    for field, errs in e.message_dict.items():
                        for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    form.add_error(None, str(e))
                return self.form_invalid(form)
            raise
        self.object = permit
        messages.success(self.request, 'Permit created successfully')
        return redirect('dashboard:vehicles_detail', pk=self.vehicle.pk)


class CustomerListView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Customer
    template_name = 'dashboard/customers_list.html'
    context_object_name = 'customers'
    paginate_by = 25

    def get_queryset(self):
        # Tenant-scoped list of all customers (individuals and companies),
        # independent of whether they already have vehicles. Vehicle-level
        # access control is enforced in vehicle/policy views.
        qs = (
            Customer.objects
            .filter(tenant=self.request.tenant, deleted_at__isnull=True)
            .annotate(vehicle_count=Count('vehicles', filter=Q(vehicles__deleted_at__isnull=True), distinct=True))
            .only('customer_type', 'first_name', 'last_name', 'company_name', 'email', 'phone', 'created_at')
            .order_by('-created_at')
        )
        customer_type = (self.request.GET.get('customer_type') or '').strip()
        if customer_type in ('individual', 'company'):
            qs = qs.filter(customer_type=customer_type)
        has_vehicles = (self.request.GET.get('has_vehicles') or '').strip()
        if has_vehicles == 'yes':
            qs = qs.filter(vehicles__deleted_at__isnull=True).distinct()
        elif has_vehicles == 'no':
            qs = qs.filter(vehicles__isnull=True)
        created_from = (self.request.GET.get('created_from') or '').strip()
        created_to = (self.request.GET.get('created_to') or '').strip()
        if created_from:
            try:
                from_date = timezone.datetime.fromisoformat(created_from).date()
                qs = qs.filter(created_at__date__gte=from_date)
            except Exception:
                pass
        if created_to:
            try:
                to_date = timezone.datetime.fromisoformat(created_to).date()
                qs = qs.filter(created_at__date__lte=to_date)
            except Exception:
                pass
        q = (self.request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(company_name__icontains=q)
                | Q(email__icontains=q) | Q(phone__icontains=q) | Q(id_number__icontains=q)
                | Q(registration_number__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['onboarding_needed'] = onboarding_service.needs_onboarding(tenant=self.request.tenant)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()
        ctx['current_customer_type'] = (self.request.GET.get('customer_type') or '').strip()
        ctx['current_has_vehicles'] = (self.request.GET.get('has_vehicles') or '').strip()
        ctx['created_from'] = (self.request.GET.get('created_from') or '').strip()
        ctx['created_to'] = (self.request.GET.get('created_to') or '').strip()
        return ctx


class CustomerExportView(TenantRoleRequiredMixin, View):
    allowed_roles = ('admin', 'manager')

    def get(self, request, *args, **kwargs):
        qs = (
            Customer.objects
            .filter(tenant=request.tenant, deleted_at__isnull=True)
            .annotate(vehicle_count=Count('vehicles', filter=Q(vehicles__deleted_at__isnull=True), distinct=True))
            .only('customer_type', 'first_name', 'last_name', 'company_name', 'email', 'phone', 'created_at')
        )
        customer_type = (request.GET.get('customer_type') or '').strip()
        if customer_type in ('individual', 'company'):
            qs = qs.filter(customer_type=customer_type)
        has_vehicles = (request.GET.get('has_vehicles') or '').strip()
        if has_vehicles == 'yes':
            qs = qs.filter(vehicles__deleted_at__isnull=True).distinct()
        elif has_vehicles == 'no':
            qs = qs.filter(vehicles__isnull=True)
        created_from = (request.GET.get('created_from') or '').strip()
        created_to = (request.GET.get('created_to') or '').strip()
        if created_from:
            try:
                from_date = timezone.datetime.fromisoformat(created_from).date()
                qs = qs.filter(created_at__date__gte=from_date)
            except Exception:
                pass
        if created_to:
            try:
                to_date = timezone.datetime.fromisoformat(created_to).date()
                qs = qs.filter(created_at__date__lte=to_date)
            except Exception:
                pass
        q = (request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(company_name__icontains=q)
                | Q(email__icontains=q) | Q(phone__icontains=q) | Q(id_number__icontains=q)
                | Q(registration_number__icontains=q)
            )

        import csv

        response = HttpResponse(content_type='text/csv')
        filename = f"customers-{request.tenant.id}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Type', 'Name', 'Email', 'Phone', 'Vehicles', 'Created'])
        for c in qs.order_by('-created_at')[:5000]:
            if c.customer_type == Customer.CUSTOMER_TYPE_INDIVIDUAL:
                name = f"{c.first_name} {c.last_name}".strip()
            else:
                name = c.company_name
            writer.writerow([
                c.get_customer_type_display(),
                name,
                c.email,
                c.phone,
                getattr(c, 'vehicle_count', 0),
                c.created_at.isoformat() if c.created_at else '',
            ])

        return response


class CustomerCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = CustomerForm
    template_name = 'dashboard/customers_form.html'
    success_url = reverse_lazy('dashboard:customers_list')

    def form_valid(self, form):
        data = form.cleaned_data
        # Dynamic Fields validation (required checks) before creating
        defs = FieldDefinition.objects.filter(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_CUSTOMER, is_active=True)
        missing = []
        for d in defs:
            raw = self.request.POST.get(f"df_{d.key}")
            if d.is_required:
                if d.data_type in ('text', 'dropdown'):
                    if not (raw and str(raw).strip()):
                        missing.append(d.name)
                elif d.data_type in ('number', 'date'):
                    if not (raw and str(raw).strip()):
                        missing.append(d.name)
                elif d.data_type == 'boolean':
                    # Expect 'true' or 'false' from select
                    if raw not in ('true', 'false'):
                        missing.append(d.name)
        if missing:
            form.add_error(None, f"Please fill required additional fields: {', '.join(missing)}")
            return self.form_invalid(form)

        try:
            customer = customer_service.create_customer(
                created_by=self.request.user,
                customer_type=data['customer_type'],
                email=data['email'],
                phone=data['phone'],
                **{k: v for k, v in data.items() if k not in ['customer_type', 'email', 'phone']}
            )
        except ValidationError as exc:
            # Map service-layer validation errors back onto the form for a clean UX
            if isinstance(getattr(exc, 'message_dict', None), dict):
                for field, errs in exc.message_dict.items():
                    messages_list = errs if isinstance(errs, (list, tuple)) else [errs]
                    if field == '__all__' or field not in form.fields:
                        for msg in messages_list:
                            form.add_error(None, msg)
                    else:
                        for msg in messages_list:
                            form.add_error(field, msg)
            else:
                for msg in getattr(exc, 'messages', [str(exc)]):
                    form.add_error(None, msg)
            return self.form_invalid(form)

        self.object = customer
        # Save dynamic fields (if provided)
        values = {d.key: self.request.POST.get(f"df_{d.key}") for d in defs}
        df_services.bulk_set_by_keys(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_CUSTOMER, obj=customer, values=values)
        if "save_add_vehicle" in self.request.POST:
            messages.success(self.request, 'Customer created. You can now add a vehicle for this owner.')
            from django.urls import reverse_lazy as _reverse_lazy  # local alias to avoid circular imports
            return redirect(f"{_reverse_lazy('dashboard:vehicles_create')}?owner={customer.pk}")
        messages.success(self.request, 'Customer created successfully')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['df_defs'] = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_CUSTOMER,
            is_active=True,
        ).order_by('order', 'name')
        # Preserve posted values when re-rendering on validation errors
        if self.request.method == 'POST':
            ctx['df_values'] = {d.key: self.request.POST.get(f"df_{d.key}") for d in ctx['df_defs']}
        else:
            ctx['df_values'] = {}
        return ctx


class PolicyRenewView(TenantRoleRequiredMixin, TenantScopedQuerysetMixin, FormView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = PolicyForm
    template_name = 'dashboard/policies_form.html'
    success_url = reverse_lazy('dashboard:policies_list')

    def get_queryset(self):
        qs = Policy.objects.select_related('vehicle', 'vehicle__owner')
        qs = self.filter_for_tenant(qs)
        allowed = vehicle_access_service.get_allowed_vehicle_types_for_user(self.request.user)
        if allowed:
            qs = qs.filter(vehicle__vehicle_type__in=allowed)
        return qs

    def dispatch(self, request, *args, **kwargs):
        self.policy = get_object_or_404(self.get_queryset(), pk=kwargs.get('pk'))
        if self.policy.status != Policy.STATUS_ACTIVE:
            messages.error(request, 'Only active policies can be renewed after full payment.')
            return redirect('dashboard:policies_detail', pk=self.policy.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        owner_id = (self.request.GET.get('owner') or '').strip()
        if owner_id:
            owner = Customer.objects.filter(
                tenant=self.request.tenant,
                deleted_at__isnull=True,
                pk=owner_id,
            ).first()
            if owner:
                kwargs['default_owner'] = owner
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        owner_id = (self.request.POST.get('owner') or self.request.GET.get('owner') or '').strip()
        owner = None
        if owner_id:
            owner = Customer.objects.filter(
                tenant=self.request.tenant,
                deleted_at__isnull=True,
                pk=owner_id,
            ).first()
        ctx['owner_context'] = owner
        return ctx

    def get_initial(self):
        initial = super().get_initial()
        existing = self.policy
        duration = existing.end_date - existing.start_date
        new_start = existing.end_date + timedelta(days=1)
        new_end = new_start + duration
        initial.update({
            'vehicle': existing.vehicle,
            'start_date': new_start,
            'end_date': new_end,
            'premium_amount': existing.premium_amount,
            'coverage_amount': existing.coverage_amount,
            'policy_type': existing.policy_type,
            'notes': f"Renewal of {existing.policy_number}",
        })
        return initial

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['vehicle'].disabled = True
        form.fields['vehicle'].required = False
        form.fields['coverage_amount'].disabled = True
        form.fields['coverage_amount'].required = False
        form.fields['policy_type'].disabled = True
        form.fields['policy_type'].required = False
        return form

    def form_valid(self, form):
        d = form.cleaned_data
        vehicle_access_service.ensure_user_can_access_vehicle(user=self.request.user, vehicle=self.policy.vehicle)
        try:
            policy_service.renew_policy(
                created_by=self.request.user,
                existing_policy=self.policy,
                new_start_date=d['start_date'],
                new_end_date=d['end_date'],
                new_premium_amount=d['premium_amount'],
                notes=d.get('notes', ''),
            )
        except ValidationError as exc:
            if isinstance(exc.message_dict, dict):
                for field, errs in exc.message_dict.items():
                    for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                        form.add_error(field if field in form.fields else None, msg)
            else:
                form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, 'Policy renewed (pending payment)')
        return redirect(self.get_success_url())


class CustomerUpdateView(TenantRoleRequiredMixin, UpdateView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Customer
    form_class = CustomerForm
    template_name = 'dashboard/customers_form.html'
    success_url = reverse_lazy('dashboard:customers_list')

    def get_queryset(self):
        # Tenant-scoped edit access: any customer in the tenant can be edited.
        # Vehicle-level access control is enforced in vehicle/policy views.
        return Customer.objects.filter(tenant=self.request.tenant, deleted_at__isnull=True)

    def form_valid(self, form):
        customer = form.instance
        data = form.cleaned_data
        # Pre-validate required dynamic fields on update as well
        defs = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_CUSTOMER,
            is_active=True,
        )
        missing = []
        for d in defs:
            raw = self.request.POST.get(f"df_{d.key}")
            if d.is_required:
                if d.data_type in ('text', 'dropdown', 'number', 'date'):
                    if not (raw and str(raw).strip()):
                        missing.append(d.name)
                elif d.data_type == 'boolean':
                    if raw not in ('true', 'false'):
                        missing.append(d.name)
        if missing:
            form.add_error(None, f"Please fill required additional fields: {', '.join(missing)}")
            return self.form_invalid(form)

        try:
            customer_service.update_customer(
                updated_by=self.request.user,
                customer=customer,
                **data,
            )
        except ValidationError as exc:
            # Surface service-layer validation back to the user instead of a 500
            if isinstance(getattr(exc, 'message_dict', None), dict):
                for field, errs in exc.message_dict.items():
                    messages_list = errs if isinstance(errs, (list, tuple)) else [errs]
                    if field == '__all__' or field not in form.fields:
                        for msg in messages_list:
                            form.add_error(None, msg)
                    else:
                        for msg in messages_list:
                            form.add_error(field, msg)
            else:
                for msg in getattr(exc, 'messages', [str(exc)]):
                    form.add_error(None, msg)
            return self.form_invalid(form)

        self.object = customer
        # Save dynamic fields updates
        values = {d.key: self.request.POST.get(f"df_{d.key}") for d in defs}
        df_services.bulk_set_by_keys(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_CUSTOMER, obj=customer, values=values)
        messages.success(self.request, 'Customer updated successfully')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['df_defs'] = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_CUSTOMER,
            is_active=True,
        ).order_by('order', 'name')
        # Preserve POSTed values on validation errors; otherwise prefill from object
        if self.request.method == 'POST':
            ctx['df_values'] = {d.key: self.request.POST.get(f"df_{d.key}") for d in ctx['df_defs']}
        else:
            obj = getattr(self, 'object', None) or ctx.get('object')
            if obj:
                values = {}
                for d in ctx['df_defs']:
                    try:
                        values[d.key] = df_services.get_field_value(definition=d, obj=obj)
                    except Exception:
                        values[d.key] = None
                ctx['df_values'] = values
            else:
                ctx['df_values'] = {}
        return ctx


class CustomerSoftDeleteView(TenantRoleRequiredMixin, View):
    allowed_roles = ('admin', 'manager')

    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk, tenant=request.tenant, deleted_at__isnull=True)
        try:
            customer_service.soft_delete_customer(deleted_by=request.user, customer=customer)
        except ValidationError as exc:
            if isinstance(getattr(exc, 'message_dict', None), dict):
                for errs in exc.message_dict.values():
                    for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                        messages.error(request, msg)
            else:
                for msg in getattr(exc, 'messages', [str(exc)]):
                    messages.error(request, msg)
            return redirect(reverse_lazy('dashboard:customers_list'))
        messages.warning(request, 'Customer deleted')
        return redirect(reverse_lazy('dashboard:customers_list'))


class VehicleListView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Vehicle
    template_name = 'dashboard/vehicles_list.html'
    context_object_name = 'vehicles'
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Vehicle.objects
            .select_related('owner')
            .only(
                'registration_number', 'vehicle_type', 'make', 'model', 'year',
                'owner__customer_type', 'owner__first_name', 'owner__last_name', 'owner__company_name',
                'created_at'
            )
            .order_by('-created_at')
        )
        qs = vehicle_access_service.filter_vehicle_queryset_for_user(user=self.request.user, queryset=qs)
        owner_id = (self.request.GET.get('owner') or '').strip()
        if owner_id:
            owner = Customer.objects.filter(
                tenant=self.request.tenant,
                deleted_at__isnull=True,
                pk=owner_id,
            ).first()
            if owner:
                qs = qs.filter(owner=owner)
        vehicle_type = (self.request.GET.get('vehicle_type') or '').strip()
        if vehicle_type:
            qs = qs.filter(vehicle_type=vehicle_type)
        compliance = (self.request.GET.get('compliance') or '').strip()
        if compliance in (
            VehicleComplianceService.STATUS_COMPLIANT,
            VehicleComplianceService.STATUS_AT_RISK,
            VehicleComplianceService.STATUS_NON_COMPLIANT,
        ):
            tenant = getattr(self.request, 'tenant', None)
            risk_days = 30
            if tenant:
                try:
                    risk_days = int(tenant.get_setting('expiry_reminder_days', 30))
                except Exception:
                    risk_days = 30
            matching_ids = []
            for v in qs:
                try:
                    result = VehicleComplianceService.compute_compliance_status(
                        vehicle=v,
                        risk_window_days=risk_days,
                    )
                except Exception:
                    continue
                if result.get('status') == compliance:
                    matching_ids.append(v.pk)
            qs = qs.filter(pk__in=matching_ids)
        created_from = (self.request.GET.get('created_from') or '').strip()
        created_to = (self.request.GET.get('created_to') or '').strip()
        if created_from:
            try:
                from_date = timezone.datetime.fromisoformat(created_from).date()
                qs = qs.filter(created_at__date__gte=from_date)
            except Exception:
                pass
        if created_to:
            try:
                to_date = timezone.datetime.fromisoformat(created_to).date()
                qs = qs.filter(created_at__date__lte=to_date)
            except Exception:
                pass
        q = (self.request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(registration_number__icontains=q)
                | Q(make__icontains=q) | Q(model__icontains=q)
                | Q(owner__first_name__icontains=q) | Q(owner__last_name__icontains=q) | Q(owner__company_name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['onboarding_needed'] = onboarding_service.needs_onboarding(tenant=self.request.tenant)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()
        ctx['current_vehicle_type'] = (self.request.GET.get('vehicle_type') or '').strip()
        ctx['current_compliance'] = (self.request.GET.get('compliance') or '').strip()
        ctx['owner_filter'] = None
        owner_id = (self.request.GET.get('owner') or '').strip()
        if owner_id:
            ctx['owner_filter'] = Customer.objects.filter(
                tenant=self.request.tenant,
                deleted_at__isnull=True,
                pk=owner_id,
            ).first()
        ctx['created_from'] = (self.request.GET.get('created_from') or '').strip()
        ctx['created_to'] = (self.request.GET.get('created_to') or '').strip()
        # Compute lightweight compliance info for vehicles on the current page
        vehicles = ctx.get('vehicles') or []
        tenant = getattr(self.request, 'tenant', None)
        risk_days = 30
        if tenant:
            try:
                risk_days = int(tenant.get_setting('expiry_reminder_days', 30))
            except Exception:
                risk_days = 30
        compliance_by_vehicle = {}
        for v in vehicles:
            try:
                result = VehicleComplianceService.compute_compliance_status(
                    vehicle=v,
                    risk_window_days=risk_days,
                )
            except Exception:
                continue
            issues = result.get('issues') or []
            expiring = result.get('expiring_soon') or []
            short_message = ''
            if expiring:
                short_message = expiring[0]
            elif issues:
                short_message = issues[0]
            compliance_by_vehicle[v.pk] = {
                'status': result.get('status'),
                'short_message': short_message,
            }
        ctx['compliance_by_vehicle'] = compliance_by_vehicle
        ctx['risk_window_days'] = risk_days
        # Provide vehicle type choices for the dropdown (from model choices)
        from apps.core.models.vehicle import Vehicle
        ctx['vehicle_type_choices'] = Vehicle.VEHICLE_TYPE_CHOICES
        return ctx


class VehicleExportView(TenantRoleRequiredMixin, View):
    allowed_roles = ('admin', 'manager')

    def get(self, request, *args, **kwargs):
        qs = (
            Vehicle.objects
            .select_related('owner')
            .only(
                'registration_number', 'vehicle_type', 'make', 'model', 'year',
                'owner__customer_type', 'owner__first_name', 'owner__last_name', 'owner__company_name',
                'created_at'
            )
        )
        qs = vehicle_access_service.filter_vehicle_queryset_for_user(user=request.user, queryset=qs)
        owner_id = (request.GET.get('owner') or '').strip()
        if owner_id:
            owner = Customer.objects.filter(
                tenant=request.tenant,
                deleted_at__isnull=True,
                pk=owner_id,
            ).first()
            if owner:
                qs = qs.filter(owner=owner)
        vehicle_type = (request.GET.get('vehicle_type') or '').strip()
        if vehicle_type:
            qs = qs.filter(vehicle_type=vehicle_type)
        created_from = (request.GET.get('created_from') or '').strip()
        created_to = (request.GET.get('created_to') or '').strip()
        if created_from:
            try:
                from_date = timezone.datetime.fromisoformat(created_from).date()
                qs = qs.filter(created_at__date__gte=from_date)
            except Exception:
                pass
        if created_to:
            try:
                to_date = timezone.datetime.fromisoformat(created_to).date()
                qs = qs.filter(created_at__date__lte=to_date)
            except Exception:
                pass
        q = (request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(registration_number__icontains=q)
                | Q(make__icontains=q) | Q(model__icontains=q)
                | Q(owner__first_name__icontains=q) | Q(owner__last_name__icontains=q) | Q(owner__company_name__icontains=q)
            )

        import csv

        response = HttpResponse(content_type='text/csv')
        filename = f"vehicles-{request.tenant.id}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Registration', 'Type', 'Make', 'Model', 'Owner', 'Year', 'Created'])
        for v in qs.order_by('-created_at')[:5000]:
            if v.owner.customer_type == 'individual':
                owner_name = f"{v.owner.first_name} {v.owner.last_name}".strip()
            else:
                owner_name = v.owner.company_name
            writer.writerow([
                v.registration_number,
                v.get_vehicle_type_display(),
                v.make,
                v.model,
                owner_name,
                v.year,
                v.created_at.isoformat() if v.created_at else '',
            ])

        return response


class VehicleDetailView(TenantRoleRequiredMixin, DetailView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Vehicle
    template_name = 'dashboard/vehicle_detail.html'
    context_object_name = 'vehicle'

    def get_queryset(self):
        qs = Vehicle.objects.select_related('owner')
        return vehicle_access_service.filter_vehicle_queryset_for_user(user=self.request.user, queryset=qs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        vehicle = ctx.get('vehicle')
        tenant = getattr(self.request, 'tenant', None)
        from django.utils import timezone
        ctx['today'] = timezone.now().date()
        
        # Get risk window from tenant settings
        risk_days = 30
        if tenant:
            try:
                risk_days = int(tenant.get_setting('expiry_reminder_days', 30))
            except Exception:
                risk_days = 30

        # Compute compliance status for this vehicle
        compliance_status = VehicleComplianceService.compute_compliance_status(
            vehicle=vehicle,
            risk_window_days=risk_days
        )
        ctx['compliance_status'] = compliance_status

        # Unified compliance snapshot (insurance + LATRA + permits)
        snapshot = VehicleComplianceService.get_compliance_snapshot(vehicle=vehicle)
        ctx['active_insurance'] = snapshot.get('active_insurance')
        ctx['active_latra'] = snapshot.get('active_latra')
        ctx['active_permits'] = snapshot.get('active_permits')

        # Full history per type for this vehicle
        ctx['policies'] = (
            Policy.objects
            .filter(vehicle=vehicle)
            .order_by('-created_at')
        )
        ctx['latra_records'] = (
            LATRARecord.objects
            .filter(vehicle=vehicle)
            .order_by('-start_date')
        )
        ctx['permits'] = (
            VehiclePermit.objects
            .select_related('permit_type')
            .filter(vehicle=vehicle)
            .order_by('-start_date')
        )

        # Simple tab selection (insurance / latra / permits)
        tab = (self.request.GET.get('tab') or 'insurance').lower()
        if tab not in ('insurance', 'latra', 'permits'):
            tab = 'insurance'
        ctx['active_tab'] = tab

        return ctx


class VehicleCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = VehicleForm
    template_name = 'dashboard/vehicles_form.html'
    success_url = reverse_lazy('dashboard:vehicles_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        owner_id = (self.request.GET.get('owner') or '').strip()
        if owner_id:
            owner = Customer.objects.filter(
                tenant=self.request.tenant,
                deleted_at__isnull=True,
                pk=owner_id,
            ).first()
            if owner:
                kwargs['default_owner'] = owner
        return kwargs

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            vehicle_access_service.ensure_user_can_use_vehicle_type(user=self.request.user, vehicle_type=d['vehicle_type'])
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError):
                form.add_error('vehicle_type', e.message_dict.get('vehicle_type', str(e)))
                return self.form_invalid(form)
            raise
        # Dynamic Fields validation for Vehicle
        defs = FieldDefinition.objects.filter(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_VEHICLE, is_active=True)
        missing = []
        for df in defs:
            raw = self.request.POST.get(f"df_{df.key}")
            if df.is_required:
                if df.data_type in ('text', 'dropdown'):
                    if not (raw and str(raw).strip()):
                        missing.append(df.name)
                elif df.data_type in ('number', 'date'):
                    if not (raw and str(raw).strip()):
                        missing.append(df.name)
                elif df.data_type == 'boolean':
                    if raw not in ('true', 'false'):
                        missing.append(df.name)
        if missing:
            form.add_error(None, f"Please fill required additional fields: {', '.join(missing)}")
            return self.form_invalid(form)
        try:
            v = vehicle_service.create_vehicle(
                created_by=self.request.user,
                owner=d['owner'],
                vehicle_type=d['vehicle_type'],
                registration_number=d['registration_number'],
                make=d['make'],
                model=d['model'],
                year=d['year'],
                color=d.get('color'),
                chassis_number=d.get('chassis_number'),
                engine_number=d.get('engine_number'),
                seating_capacity=d.get('seating_capacity'),
                engine_capacity=d.get('engine_capacity'),
                notes=d.get('notes'),
            )
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError):
                # Map validation errors to form
                if isinstance(e.message_dict, dict):
                    for field, errs in e.message_dict.items():
                        for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    form.add_error(None, str(e))
                return self.form_invalid(form)
            raise
        self.object = v
        # Save dynamic fields
        values = {df.key: self.request.POST.get(f"df_{df.key}") for df in defs}
        df_services.bulk_set_by_keys(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_VEHICLE, obj=v, values=values)
        if "save_add_insurance" in self.request.POST:
            from django.urls import reverse_lazy as _reverse_lazy  # local alias to avoid circular imports
            messages.success(self.request, 'Vehicle created. You can now add an insurance policy.')
            return redirect(f"{_reverse_lazy('dashboard:policies_create')}?vehicle={v.pk}")
        if "save_add_another" in self.request.POST:
            messages.success(self.request, 'Vehicle created. You can add another.')
            return redirect("dashboard:vehicles_create")
        messages.success(self.request, 'Vehicle created successfully')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['df_defs'] = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_VEHICLE,
            is_active=True,
        ).order_by('order', 'name')
        if self.request.method == 'POST':
            ctx['df_values'] = {d.key: self.request.POST.get(f"df_{d.key}") for d in ctx['df_defs']}
        else:
            ctx['df_values'] = {}
        return ctx


class VehicleUpdateView(TenantRoleRequiredMixin, UpdateView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Vehicle
    form_class = VehicleForm
    template_name = 'dashboard/vehicles_form.html'
    success_url = reverse_lazy('dashboard:vehicles_list')

    def get_queryset(self):
        qs = Vehicle.objects.select_related('owner')
        return vehicle_access_service.filter_vehicle_queryset_for_user(user=self.request.user, queryset=qs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        v = form.instance
        d = form.cleaned_data
        try:
            vehicle_access_service.ensure_user_can_access_vehicle(user=self.request.user, vehicle=v)
            if 'vehicle_type' in d:
                vehicle_access_service.ensure_user_can_use_vehicle_type(user=self.request.user, vehicle_type=d['vehicle_type'])
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError):
                form.add_error('vehicle_type', e.message_dict.get('vehicle_type', str(e)))
                return self.form_invalid(form)
            raise
        # Pre-validate required dynamic fields on update
        defs = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_VEHICLE,
            is_active=True,
        )
        missing = []
        for df in defs:
            raw = self.request.POST.get(f"df_{df.key}")
            if df.is_required:
                if df.data_type in ('text', 'dropdown', 'number', 'date'):
                    if not (raw and str(raw).strip()):
                        missing.append(df.name)
                elif df.data_type == 'boolean':
                    if raw not in ('true', 'false'):
                        missing.append(df.name)
        if missing:
            form.add_error(None, f"Please fill required additional fields: {', '.join(missing)}")
            return self.form_invalid(form)

        vehicle_service.update_vehicle(
            updated_by=self.request.user,
            vehicle=v,
            **d,
        )
        self.object = v
        # Save dynamic fields updates
        values = {df.key: self.request.POST.get(f"df_{df.key}") for df in defs}
        df_services.bulk_set_by_keys(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_VEHICLE,
            obj=v,
            values=values,
        )

        # Support the same post-save actions as vehicle creation
        if "save_add_insurance" in self.request.POST:
            from django.urls import reverse_lazy as _reverse_lazy
            messages.success(self.request, 'Vehicle updated. You can now add an insurance policy.')
            return redirect(f"{_reverse_lazy('dashboard:policies_create')}?vehicle={v.pk}")

        if "save_add_another" in self.request.POST:
            messages.success(self.request, 'Vehicle updated. You can now add another vehicle.')
            return redirect("dashboard:vehicles_create")

        messages.success(self.request, 'Vehicle updated successfully')
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['df_defs'] = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_VEHICLE,
            is_active=True,
        ).order_by('order', 'name')
        if self.request.method == 'POST':
            ctx['df_values'] = {d.key: self.request.POST.get(f"df_{d.key}") for d in ctx['df_defs']}
        else:
            obj = getattr(self, 'object', None) or ctx.get('object')
            if obj:
                values = {}
                for d in ctx['df_defs']:
                    try:
                        values[d.key] = df_services.get_field_value(definition=d, obj=obj)
                    except Exception:
                        values[d.key] = None
                ctx['df_values'] = values
            else:
                ctx['df_values'] = {}
        return ctx


class VehicleSoftDeleteView(TenantRoleRequiredMixin, View):
    allowed_roles = ('admin', 'manager')

    def post(self, request, pk):
        v = get_object_or_404(Vehicle, pk=pk)
        vehicle_access_service.ensure_user_can_access_vehicle(user=request.user, vehicle=v)
        vehicle_service.soft_delete_vehicle(deleted_by=request.user, vehicle=v)
        messages.warning(request, 'Vehicle deleted')
        return redirect(reverse_lazy('dashboard:vehicles_list'))


class VehicleBulkImportView(TenantRoleRequiredMixin, FormView):
    allowed_roles = ('admin', 'manager')
    template_name = 'dashboard/vehicles_import.html'
    form_class = VehicleBulkImportForm
    success_url = reverse_lazy('dashboard:vehicles_import')

    def post(self, request, *args, **kwargs):
        form = self.get_form()
        if form.is_valid():
            result = vehicle_import_service.import_vehicles_from_csv(
                tenant=request.tenant,
                user=request.user,
                file_obj=form.cleaned_data['file'],
            )
            created = result.get('created', 0)
            errors = result.get('errors', [])
            if errors:
                messages.warning(request, f"Imported {created} vehicle(s) with {len(errors)} error(s).")
            else:
                messages.success(request, f"Successfully imported {created} vehicle(s).")
            ctx = self.get_context_data(form=form, result=result)
            return self.render_to_response(ctx)
        return self.form_invalid(form)


class PolicyListView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Policy
    template_name = 'dashboard/policies_list.html'
    context_object_name = 'policies'
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Policy.objects.filter(tenant=self.request.tenant)
            .select_related('vehicle', 'vehicle__owner')
            .only(
                'policy_number', 'status', 'start_date', 'end_date', 'premium_amount',
                'vehicle__registration_number', 'vehicle__make', 'vehicle__model',
                'vehicle__owner__customer_type', 'vehicle__owner__first_name', 'vehicle__owner__last_name', 'vehicle__owner__company_name',
                'created_at'
            )
            .order_by('-created_at')
        )
        allowed = vehicle_access_service.get_allowed_vehicle_types_for_user(self.request.user)
        if allowed:
            qs = qs.filter(vehicle__vehicle_type__in=allowed)
        q = (self.request.GET.get('q') or '').strip()
        status = (self.request.GET.get('status') or '').strip()
        if q:
            qs = qs.filter(
                Q(policy_number__icontains=q)
                | Q(vehicle__registration_number__icontains=q)
                | Q(vehicle__owner__first_name__icontains=q)
                | Q(vehicle__owner__last_name__icontains=q)
                | Q(vehicle__owner__company_name__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['onboarding_needed'] = onboarding_service.needs_onboarding(tenant=self.request.tenant)
        params = self.request.GET.copy()
        params.pop('page', None)
        ctx['querystring'] = params.urlencode()

        tenant = getattr(self.request, 'tenant', None)
        risk_days = 30
        if tenant is not None:
            try:
                risk_days = int(tenant.get_setting('expiry_reminder_days', 30))
            except Exception:
                risk_days = 30

        today = timezone.now().date()
        soon = today + timedelta(days=risk_days)
        policies = ctx.get('policies') or ctx.get('object_list')
        expiring_ids = []
        if policies is not None:
            for p in policies:
                if getattr(p, 'status', None) == Policy.STATUS_ACTIVE and p.end_date > today and p.end_date <= soon:
                    expiring_ids.append(p.id)
        ctx['expiring_policy_ids'] = expiring_ids
        ctx['risk_window_days'] = risk_days
        return ctx


class PolicyCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = PolicyForm
    template_name = 'dashboard/policies_form.html'
    success_url = reverse_lazy('dashboard:policies_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        vehicle_id = self.request.GET.get('vehicle')
        if vehicle_id:
            try:
                vehicle = Vehicle.objects.filter(tenant=self.request.tenant).get(pk=vehicle_id)
                vehicle_access_service.ensure_user_can_access_vehicle(
                    user=self.request.user,
                    vehicle=vehicle,
                )
                initial['vehicle'] = vehicle
            except Vehicle.DoesNotExist:
                pass
            except Exception:
                # If access is denied or any other validation fails, fall back to default initial
                pass
        return initial

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            vehicle_access_service.ensure_user_can_access_vehicle(user=self.request.user, vehicle=d['vehicle'])
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError):
                form.add_error('vehicle', e.message_dict.get('vehicle', str(e)))
                return self.form_invalid(form)
            raise
        # Dynamic Fields validation for Policy
        defs = FieldDefinition.objects.filter(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_POLICY, is_active=True)
        missing = []
        for df in defs:
            raw = self.request.POST.get(f"df_{df.key}")
            if df.is_required:
                if df.data_type in ('text', 'dropdown'):
                    if not (raw and str(raw).strip()):
                        missing.append(df.name)
                elif df.data_type in ('number', 'date'):
                    if not (raw and str(raw).strip()):
                        missing.append(df.name)
                elif df.data_type == 'boolean':
                    if raw not in ('true', 'false'):
                        missing.append(df.name)
        if missing:
            form.add_error(None, f"Please fill required additional fields: {', '.join(missing)}")
            return self.form_invalid(form)
        p = policy_service.create_policy(
            created_by=self.request.user,
            vehicle=d['vehicle'],
            start_date=d['start_date'],
            end_date=d['end_date'],
            premium_amount=d['premium_amount'],
            coverage_amount=d.get('coverage_amount'),
            policy_type=d.get('policy_type', ''),
            notes=d.get('notes', ''),
        )
        self.object = p
        # Save dynamic fields
        values = {df.key: self.request.POST.get(f"df_{df.key}") for df in defs}
        df_services.bulk_set_by_keys(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_POLICY, obj=p, values=values)
        messages.success(self.request, f"Policy {p.policy_number} created (pending payment). You can now record a payment from the policies list or the payments page.")
        return redirect(self.get_success_url())

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['df_defs'] = FieldDefinition.objects.filter(
            tenant=self.request.tenant,
            entity_type=FieldDefinition.ENTITY_POLICY,
            is_active=True,
        ).order_by('order', 'name')
        if self.request.method == 'POST':
            ctx['df_values'] = {d.key: self.request.POST.get(f"df_{d.key}") for d in ctx['df_defs']}
        else:
            ctx['df_values'] = {}

        selected_vehicle = None
        form = ctx.get('form')
        if form is not None:
            vehicle_value = None
            if form.is_bound:
                vehicle_value = form.data.get(form.add_prefix('vehicle')) or form.data.get('vehicle')
            else:
                vehicle_value = form.initial.get('vehicle') or getattr(form.instance, 'vehicle', None)
            if vehicle_value:
                try:
                    if isinstance(vehicle_value, Vehicle):
                        selected_vehicle = vehicle_value
                    else:
                        selected_vehicle = (
                            Vehicle.objects.filter(tenant=self.request.tenant)
                            .select_related('owner')
                            .get(pk=vehicle_value)
                        )
                    vehicle_access_service.ensure_user_can_access_vehicle(
                        user=self.request.user,
                        vehicle=selected_vehicle,
                    )
                except Exception:
                    selected_vehicle = None

        if selected_vehicle is not None:
            ctx['selected_vehicle'] = selected_vehicle
            try:
                ctx['active_policy_for_vehicle'] = VehicleComplianceService.get_active_insurance(vehicle=selected_vehicle)
            except Exception:
                ctx['active_policy_for_vehicle'] = None
        else:
            ctx['selected_vehicle'] = None
            ctx['active_policy_for_vehicle'] = None

        return ctx


class PolicyReportView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager')
    model = Policy
    template_name = 'dashboard/policies_report.html'
    context_object_name = 'policies'
    paginate_by = 50

    def get_queryset(self):
        qs = Policy.objects.filter(tenant=self.request.tenant).select_related('vehicle', 'vehicle__owner').order_by('-created_at')
        allowed = vehicle_access_service.get_allowed_vehicle_types_for_user(self.request.user)
        if allowed:
            qs = qs.filter(vehicle__vehicle_type__in=allowed)
        status = (self.request.GET.get('status') or '').strip()
        if status == 'active':
            qs = qs.filter(status=Policy.STATUS_ACTIVE)
        elif status == 'expired':
            qs = qs.filter(status=Policy.STATUS_EXPIRED)
        start_from = (self.request.GET.get('start_from') or '').strip()
        start_to = (self.request.GET.get('start_to') or '').strip()
        if start_from:
            qs = qs.filter(start_date__gte=start_from)
        if start_to:
            qs = qs.filter(start_date__lte=start_to)
        return qs

    def render_to_response(self, context, **response_kwargs):
        export = (self.request.GET.get('export') or '').strip().lower()
        if export in ('csv', 'xlsx', 'pdf'):
            qs = context['policies']
            fields = ['policy_number', 'status', 'start_date', 'end_date', 'premium_amount', 'coverage_amount', 'vehicle__registration_number']
            if export == 'csv':
                import csv
                from django.http import HttpResponse
                resp = HttpResponse(content_type='text/csv')
                resp['Content-Disposition'] = 'attachment; filename="policies.csv"'
                writer = csv.writer(resp)
                writer.writerow(['Policy #', 'Status', 'Start', 'End', 'Premium', 'Coverage', 'Vehicle'])
                for p in qs:
                    writer.writerow([p.policy_number, p.status, p.start_date, p.end_date, p.premium_amount, p.coverage_amount, p.vehicle.registration_number])
                return resp
            elif export == 'xlsx':
                try:
                    from openpyxl import Workbook
                    from django.http import HttpResponse
                    wb = Workbook()
                    ws = wb.active
                    ws.append(['Policy #', 'Status', 'Start', 'End', 'Premium', 'Coverage', 'Vehicle'])
                    for p in qs:
                        ws.append([p.policy_number, p.status, p.start_date, p.end_date, float(p.premium_amount), float(p.coverage_amount or 0), p.vehicle.registration_number])
                    from io import BytesIO
                    bio = BytesIO()
                    wb.save(bio)
                    bio.seek(0)
                    resp = HttpResponse(bio.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    resp['Content-Disposition'] = 'attachment; filename="policies.xlsx"'
                    return resp
                except Exception:
                    # Fallback to CSV if XLSX libs not available
                    import csv
                    from django.http import HttpResponse
                    resp = HttpResponse(content_type='text/csv')
                    resp['Content-Disposition'] = 'attachment; filename="policies.csv"'
                    writer = csv.writer(resp)
                    writer.writerow(['Policy #', 'Status', 'Start', 'End', 'Premium', 'Coverage', 'Vehicle'])
                    for p in qs:
                        writer.writerow([p.policy_number, p.status, p.start_date, p.end_date, p.premium_amount, p.coverage_amount, p.vehicle.registration_number])
                    return resp
            else:  # pdf
                try:
                    from io import BytesIO
                    from reportlab.lib.pagesizes import A4
                    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                    from reportlab.lib import colors
                    from reportlab.lib.styles import getSampleStyleSheet
                    from django.http import HttpResponse
                    buffer = BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                    elements = []
                    styles = getSampleStyleSheet()
                    elements.append(Paragraph('Policies Report', styles['Title']))
                    elements.append(Spacer(1, 12))
                    data = [['Policy #', 'Status', 'Start', 'End', 'Premium', 'Coverage', 'Vehicle']]
                    for p in qs:
                        data.append([str(p.policy_number), str(p.status), str(p.start_date), str(p.end_date), str(p.premium_amount), str(p.coverage_amount or ''), str(p.vehicle.registration_number)])
                    table = Table(data, repeatRows=1)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ]))
                    elements.append(table)
                    doc.build(elements)
                    pdf = buffer.getvalue()
                    buffer.close()
                    resp = HttpResponse(pdf, content_type='application/pdf')
                    resp['Content-Disposition'] = 'attachment; filename="policies.pdf"'
                    return resp
                except Exception:
                    # Fallback to CSV if PDF generation fails
                    import csv
                    from django.http import HttpResponse
                    resp = HttpResponse(content_type='text/csv')
                    resp['Content-Disposition'] = 'attachment; filename="policies.csv"'
                    writer = csv.writer(resp)
                    writer.writerow(['Policy #', 'Status', 'Start', 'End', 'Premium', 'Coverage', 'Vehicle'])
                    for p in qs:
                        writer.writerow([p.policy_number, p.status, p.start_date, p.end_date, p.premium_amount, p.coverage_amount, p.vehicle.registration_number])
                    return resp
        return super().render_to_response(context, **response_kwargs)


class SupportRequestListView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = SupportRequest
    template_name = 'dashboard/support_list.html'
    context_object_name = 'tickets'
    paginate_by = 25

    def get_queryset(self):
        qs = SupportRequest.objects.filter(tenant=self.request.tenant).only('subject', 'status', 'priority', 'created_at').order_by('-created_at')
        status = (self.request.GET.get('status') or '').strip()
        priority = (self.request.GET.get('priority') or '').strip()
        q = (self.request.GET.get('q') or '').strip()
        if status:
            qs = qs.filter(status=status)
        if priority:
            qs = qs.filter(priority=priority)
        if q:
            qs = qs.filter(subject__icontains=q)
        return qs


class SupportRequestCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = SupportRequestForm
    template_name = 'dashboard/support_form.html'
    success_url = reverse_lazy('dashboard:support_list')

    def form_valid(self, form):
        obj = form.save(commit=False)
        obj.tenant = self.request.tenant
        obj.created_by = self.request.user
        obj.updated_by = self.request.user
        obj.save()
        self.object = obj
        messages.success(self.request, 'Support request submitted')
        return redirect('dashboard:support_list')


class PolicyCancelView(TenantRoleRequiredMixin, TemplateView):
    allowed_roles = ('admin', 'manager')
    template_name = 'dashboard/policy_cancel_confirm.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.policy = get_object_or_404(Policy, pk=kwargs.get('pk'), tenant=request.tenant)
        vehicle_access_service.ensure_user_can_access_vehicle(user=request.user, vehicle=self.policy.vehicle)
        if self.policy.status not in (Policy.STATUS_ACTIVE, Policy.STATUS_PENDING_PAYMENT):
            messages.error(request, 'Only active or pending policies can be cancelled')
            return redirect('dashboard:policies_detail', pk=self.policy.pk)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['policy'] = self.policy
        ctx['reasons'] = Policy.CANCELLATION_REASON_CHOICES
        return ctx
    
    def post(self, request, *args, **kwargs):
        reason = (request.POST.get('reason') or '').strip()
        note = (request.POST.get('note') or '').strip()
        
        if not reason:
            messages.error(request, 'Cancellation reason is required')
            return self.get(request, *args, **kwargs)
        
        try:
            policy_service.cancel_policy(
                policy_id=self.policy.id,
                actor=request.user,
                reason=reason,
                note=note
            )
            messages.success(request, f'Policy {self.policy.policy_number} cancelled successfully')
        except Exception as e:
            messages.error(request, str(e))
        
        return redirect('dashboard:policies_detail', pk=self.policy.pk)


class RegistrationReportView(TenantRoleRequiredMixin, TemplateView):
    allowed_roles = ('admin', 'manager')
    template_name = 'dashboard/registrations_report.html'

    def get_context_data(self, **kwargs):
        from django.db.models.functions import TruncDate, TruncMonth
        ctx = super().get_context_data(**kwargs)
        period = (self.request.GET.get('period') or 'daily').lower()
        grouper = TruncDate('created_at') if period == 'daily' else TruncMonth('created_at')

        tenant = getattr(self.request, 'tenant', None)

        customers = (
            Customer.objects.filter(tenant=tenant)
            .annotate(g=grouper)
            .values('g')
            .order_by('g')
            .annotate(count=Count('id'))
        )
        vehicles = (
            Vehicle.objects.filter(tenant=tenant)
            .annotate(g=grouper)
            .values('g')
            .order_by('g')
            .annotate(count=Count('id'))
        )
        policies = (
            Policy.objects.filter(tenant=tenant)
            .annotate(g=grouper)
            .values('g')
            .order_by('g')
            .annotate(count=Count('id'))
        )

        allowed = vehicle_access_service.get_allowed_vehicle_types_for_user(self.request.user)
        if allowed:
            customers = customers.filter(vehicles__vehicle_type__in=allowed).distinct()
            vehicles = vehicles.filter(vehicle_type__in=allowed)
            policies = policies.filter(vehicle__vehicle_type__in=allowed)

        # Align dates across series
        dates = sorted({*[c['g'] for c in customers], *[v['g'] for v in vehicles], *[p['g'] for p in policies]})
        c_map = {x['g']: x['count'] for x in customers}
        v_map = {x['g']: x['count'] for x in vehicles}
        p_map = {x['g']: x['count'] for x in policies}
        rows = [
            {
                'date': d,
                'customers': c_map.get(d, 0),
                'vehicles': v_map.get(d, 0),
                'policies': p_map.get(d, 0),
            }
            for d in dates
        ]
        ctx.update({'rows': rows, 'period': period})
        return ctx

    def render_to_response(self, context, **response_kwargs):
        export = (self.request.GET.get('export') or '').strip().lower()
        if export in ('csv', 'xlsx', 'pdf'):
            data = context['rows']
            if export == 'csv':
                import csv
                from django.http import HttpResponse
                resp = HttpResponse(content_type='text/csv')
                resp['Content-Disposition'] = 'attachment; filename="registrations.csv"'
                w = csv.writer(resp)
                w.writerow(['Date', 'Customers', 'Vehicles', 'Policies'])
                for r in data:
                    w.writerow([r['date'], r['customers'], r['vehicles'], r['policies']])
                return resp
            elif export == 'xlsx':
                try:
                    from openpyxl import Workbook
                    from django.http import HttpResponse
                    wb = Workbook()
                    ws = wb.active
                    ws.append(['Date', 'Customers', 'Vehicles', 'Policies'])
                    for r in data:
                        ws.append([r['date'], r['customers'], r['vehicles'], r['policies']])
                    from io import BytesIO
                    bio = BytesIO()
                    wb.save(bio)
                    bio.seek(0)
                    resp = HttpResponse(bio.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    resp['Content-Disposition'] = 'attachment; filename="registrations.xlsx"'
                    return resp
                except Exception:
                    import csv
                    from django.http import HttpResponse
                    resp = HttpResponse(content_type='text/csv')
                    resp['Content-Disposition'] = 'attachment; filename="registrations.csv"'
                    w = csv.writer(resp)
                    w.writerow(['Date', 'Customers', 'Vehicles', 'Policies'])
                    for r in data:
                        w.writerow([r['date'], r['customers'], r['vehicles'], r['policies']])
                    return resp
            else:  # pdf
                try:
                    from io import BytesIO
                    from reportlab.lib.pagesizes import A4
                    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
                    from reportlab.lib import colors
                    from reportlab.lib.styles import getSampleStyleSheet
                    from django.http import HttpResponse
                    buffer = BytesIO()
                    doc = SimpleDocTemplate(buffer, pagesize=A4)
                    elements = []
                    styles = getSampleStyleSheet()
                    elements.append(Paragraph('Registrations Report', styles['Title']))
                    elements.append(Spacer(1, 12))
                    data_rows = [['Date', 'Customers', 'Vehicles', 'Policies']]
                    for r in data:
                        data_rows.append([str(r['date']), str(r['customers']), str(r['vehicles']), str(r['policies'])])
                    table = Table(data_rows, repeatRows=1)
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
                        ('GRID', (0,0), (-1,-1), 0.25, colors.grey),
                        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
                        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                    ]))
                    elements.append(table)
                    doc.build(elements)
                    pdf = buffer.getvalue()
                    buffer.close()
                    resp = HttpResponse(pdf, content_type='application/pdf')
                    resp['Content-Disposition'] = 'attachment; filename="registrations.pdf"'
                    return resp
                except Exception:
                    import csv
                    from django.http import HttpResponse
                    resp = HttpResponse(content_type='text/csv')
                    resp['Content-Disposition'] = 'attachment; filename="registrations.csv"'
                    w = csv.writer(resp)
                    w.writerow(['Date', 'Customers', 'Vehicles', 'Policies'])
                    for r in data:
                        w.writerow([r['date'], r['customers'], r['vehicles'], r['policies']])
                    return resp
        return super().render_to_response(context, **response_kwargs)


class PaymentCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = PaymentForm
    template_name = 'dashboard/payments_form.html'
    success_url = reverse_lazy('dashboard:policies_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['tenant'] = getattr(self.request, 'tenant', None)
        return kwargs

    def form_valid(self, form):
        d = form.cleaned_data
        vehicle_access_service.ensure_user_can_access_vehicle(user=self.request.user, vehicle=d['policy'].vehicle)
        user = self.request.user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            if user.role in (User.ROLE_ADMIN, User.ROLE_MANAGER):
                pay = payment_service.add_payment_and_activate_policy(
                    created_by=user,
                    policy=d['policy'],
                    amount=d['amount'],
                    payment_method=d['payment_method'],
                    reference_number=d['reference_number'],
                    payer_name=d.get('payer_name', ''),
                    notes=d.get('notes', ''),
                )
                messages.success(self.request, 'Payment recorded and verified.')
            else:
                pay = payment_service.record_payment(
                    created_by=user,
                    policy=d['policy'],
                    amount=d['amount'],
                    payment_method=d['payment_method'],
                    reference_number=d['reference_number'],
                    payer_name=d.get('payer_name', ''),
                    notes=d.get('notes', ''),
                )
                # Notify tenant admins/managers that a payment is pending verification
                from apps.notifications.services import NotificationService

                NotificationService.handle_event(
                    event_type='payment_pending_verification',
                    tenant=self.request.tenant,
                    actor=user,
                    context={
                        'policy': pay.policy,
                    },
                )
                messages.info(self.request, 'Payment recorded and is pending approval.')
        except ValidationError as exc:
            # Map payment validation errors back onto the form
            if isinstance(getattr(exc, 'message_dict', None), dict):
                for field, errs in exc.message_dict.items():
                    messages_list = errs if isinstance(errs, (list, tuple)) else [errs]
                    if field == '__all__' or field not in form.fields:
                        for msg in messages_list:
                            form.add_error(None, msg)
                    else:
                        for msg in messages_list:
                            form.add_error(field, msg)
            else:
                for msg in getattr(exc, 'messages', [str(exc)]):
                    form.add_error(None, msg)
            return self.form_invalid(form)

        self.object = pay
        return redirect(self.get_success_url())

    def get_initial(self):
        initial = super().get_initial()
        policy_id = self.request.GET.get('policy')
        if policy_id:
            try:
                policy = Policy.objects.select_related('vehicle', 'vehicle__owner').get(
                    pk=int(policy_id),
                    tenant=self.request.tenant,
                )
                vehicle_access_service.ensure_user_can_access_vehicle(user=self.request.user, vehicle=policy.vehicle)
                initial['policy'] = policy
            except Exception:
                pass
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        form = ctx.get('form')
        selected_policy = None
        from .models import Policy as PolicyModel

        if form is not None:
            # Prefer an already-resolved Policy instance from initial
            initial_policy = form.initial.get('policy')
            if isinstance(initial_policy, PolicyModel):
                selected_policy = initial_policy
            else:
                # Fall back to ID from bound data or initial
                policy_value = (form.data.get('policy') or initial_policy or '').strip()
                if policy_value:
                    try:
                        selected_policy = PolicyModel.objects.select_related('vehicle', 'vehicle__owner').get(
                            pk=int(policy_value),
                            tenant=getattr(self.request, 'tenant', None),
                        )
                        vehicle_access_service.ensure_user_can_access_vehicle(
                            user=self.request.user,
                            vehicle=selected_policy.vehicle,
                        )
                    except Exception:
                        selected_policy = None

        ctx['selected_policy'] = selected_policy
        # Simple flag to allow the template to describe behavior clearly per role
        user = self.request.user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ctx['will_auto_verify_payment'] = bool(getattr(user, 'role', None) in (User.ROLE_ADMIN, User.ROLE_MANAGER))
        return ctx


class PaymentVerifyView(TenantRoleRequiredMixin, View):
    allowed_roles = ('admin', 'manager')

    def post(self, request, pk):
        payment = get_object_or_404(Payment, pk=pk, tenant=request.tenant)
        try:
            payment_service.verify_payment(verified_by=request.user, payment=payment)
            messages.success(request, 'Payment verified.')
        except Exception as e:
            messages.error(request, str(e))
        return redirect('dashboard:policies_detail', pk=payment.policy.pk)


class PaymentReviewView(TenantRoleRequiredMixin, FormView):
    allowed_roles = ('admin', 'manager')
    form_class = PaymentReviewForm
    template_name = 'dashboard/payments_review.html'

    def dispatch(self, request, *args, **kwargs):
        self.payment = get_object_or_404(Payment, pk=kwargs.get('pk'), tenant=request.tenant)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        initial['action'] = PaymentReviewForm.ACTION_APPROVE
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['payment'] = self.payment
        ctx['policy'] = self.payment.policy
        return ctx

    def form_valid(self, form):
        from django.utils import timezone
        action = form.cleaned_data['action']
        notes = form.cleaned_data['review_notes']

        if self.payment.is_verified:
            messages.info(self.request, 'This payment has already been verified.')
            return redirect('dashboard:policies_detail', pk=self.payment.policy.pk)

        user = self.request.user

        if action == PaymentReviewForm.ACTION_APPROVE:
            try:
                payment_service.verify_payment(verified_by=user, payment=self.payment)
            except ValidationError as exc:
                messages.error(self.request, '; '.join(exc.messages))
                return self.form_invalid(form)

            if notes:
                prefix = f"[REVIEW APPROVED {timezone.now().isoformat()} by {user.get_full_name() or user.username}] "
                base = (self.payment.notes or '').strip()
                combined = (base + '\n' if base else '') + prefix + notes
                self.payment.notes = combined
                self.payment.save(update_fields=['notes', 'updated_at'])

            messages.success(self.request, 'Payment approved and verified.')
        else:
            # Reject payment: keep it unverified and record reason in notes
            prefix = f"[REJECTED {timezone.now().isoformat()} by {user.get_full_name() or user.username}] "
            base = (self.payment.notes or '').strip()
            combined = (base + '\n' if base else '') + prefix + notes
            self.payment.notes = combined
            self.payment.save(update_fields=['notes', 'updated_at'])
            messages.info(self.request, 'Payment has been marked as rejected and will not count towards policy activation.')

        return redirect('dashboard:policies_detail', pk=self.payment.policy.pk)


class StaffListView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager')
    template_name = 'dashboard/staff_list.html'
    context_object_name = 'staff'

    def get_queryset(self):
        User = get_user_model()
        qs = User.objects.filter(
            tenant=self.request.tenant,
            is_super_admin=False,
        ).order_by('role', 'username')
        role = (self.request.GET.get('role') or '').strip()
        q = (self.request.GET.get('q') or '').strip()
        if role:
            qs = qs.filter(role=role)
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(username__icontains=q)
                | Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        staff_qs = list(ctx.get('staff', []))
        staff_ids = [u.id for u in staff_qs]
        tenant = getattr(self.request, 'tenant', None)

        # Aggregate simple performance metrics per staff user, scoped to tenant
        cust_counts = dict(
            Customer.objects.filter(tenant=tenant, created_by_id__in=staff_ids)
            .values('created_by_id').annotate(c=Count('id'))
            .values_list('created_by_id', 'c')
        ) if tenant and staff_ids else {}

        veh_counts = dict(
            Vehicle.objects.filter(tenant=tenant, created_by_id__in=staff_ids)
            .values('created_by_id').annotate(c=Count('id'))
            .values_list('created_by_id', 'c')
        ) if tenant and staff_ids else {}

        pol_counts = dict(
            Policy.objects.filter(tenant=tenant, created_by_id__in=staff_ids)
            .values('created_by_id').annotate(c=Count('id'))
            .values_list('created_by_id', 'c')
        ) if tenant and staff_ids else {}

        pay_created_counts = dict(
            Payment.objects.filter(tenant=tenant, created_by_id__in=staff_ids)
            .values('created_by_id').annotate(c=Count('id'))
            .values_list('created_by_id', 'c')
        ) if tenant and staff_ids else {}

        pay_verified_counts = dict(
            Payment.objects.filter(tenant=tenant, verified_by_id__in=staff_ids)
            .values('verified_by_id').annotate(c=Count('id'))
            .values_list('verified_by_id', 'c')
        ) if tenant and staff_ids else {}

        assignments = UserVehicleTypeAssignment.objects.filter(
            tenant=self.request.tenant,
            deleted_at__isnull=True,
        ).values('user_id', 'vehicle_type')
        mapping = {}
        for row in assignments:
            mapping.setdefault(row['user_id'], []).append(row['vehicle_type'])
        label_map = {key: label for key, label in Vehicle.VEHICLE_TYPE_CHOICES}
        staff_access = []
        for staff in staff_qs:
            types = mapping.get(staff.id)
            if types:
                labels = [label_map.get(vt, vt) for vt in types]
            else:
                labels = ['All vehicle types']
            staff_access.append({
                'user': staff,
                'vehicle_types': labels,
                'metrics': {
                    'customers': cust_counts.get(staff.id, 0),
                    'vehicles': veh_counts.get(staff.id, 0),
                    'policies': pol_counts.get(staff.id, 0),
                    'payments_recorded': pay_created_counts.get(staff.id, 0),
                    'payments_verified': pay_verified_counts.get(staff.id, 0),
                },
            })
        ctx['staff_access'] = staff_access
        return ctx


class StaffCreateView(TenantRoleRequiredMixin, FormView):
    allowed_roles = ('admin',)
    form_class = StaffCreateForm
    template_name = 'dashboard/staff_form.html'
    success_url = reverse_lazy('dashboard:staff_list')

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            user = staff_service.create_staff_user(
                created_by=self.request.user,
                username=d['username'],
                email=d.get('email', ''),
                first_name=d.get('first_name', ''),
                last_name=d.get('last_name', ''),
                phone_number=d.get('phone_number', ''),
                role=d['role'],
                is_active=d.get('is_active', True),
            )
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError) and isinstance(getattr(e, 'message_dict', None), dict):
                for field, errs in e.message_dict.items():
                    for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                        form.add_error(field if field in form.fields else None, msg)
                return self.form_invalid(form)
            form.add_error(None, str(e))
            return self.form_invalid(form)
        self.object = user
        temp_password = getattr(user, '_raw_password', None)
        if temp_password:
            messages.success(
                self.request,
                f'Staff user created successfully. Initial password: {temp_password}. '
                'Ask the user to change it after first login.'
            )
        else:
            messages.success(self.request, 'Staff user created successfully')
        return redirect(self.get_success_url())


class PermitTypeListView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager')
    model = PermitType
    template_name = 'dashboard/permit_types_list.html'
    context_object_name = 'permit_types'

    def get_queryset(self):
        return PermitType.objects.filter(tenant=self.request.tenant).order_by('name')


class PermitTypeCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin',)
    form_class = PermitTypeForm
    template_name = 'dashboard/permit_types_form.html'
    success_url = reverse_lazy('dashboard:permit_types_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            pt = permit_type_service.create_permit_type(
                created_by=self.request.user,
                name=d['name'],
                is_active=d.get('is_active', True),
                conflicts_with=d.get('conflicts_with'),
            )
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError) and isinstance(getattr(e, 'message_dict', None), dict):
                for field, errs in e.message_dict.items():
                    for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                        form.add_error(field if field in form.fields else None, msg)
                return self.form_invalid(form)
            form.add_error(None, str(e))
            return self.form_invalid(form)
        self.object = pt
        messages.success(self.request, 'Permit type created successfully')
        return redirect(self.get_success_url())


class PermitTypeUpdateView(TenantRoleRequiredMixin, UpdateView):
    allowed_roles = ('admin',)
    model = PermitType
    form_class = PermitTypeForm
    template_name = 'dashboard/permit_types_form.html'
    success_url = reverse_lazy('dashboard:permit_types_list')

    def get_queryset(self):
        return PermitType.objects.filter(tenant=self.request.tenant)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['tenant'] = self.request.tenant
        return kwargs

    def form_valid(self, form):
        d = form.cleaned_data
        try:
            pt = permit_type_service.update_permit_type(
                updated_by=self.request.user,
                permit_type=self.object,
                name=d['name'],
                is_active=d.get('is_active', True),
                conflicts_with=d.get('conflicts_with'),
            )
        except Exception as e:
            from django.core.exceptions import ValidationError as DjangoValidationError
            if isinstance(e, DjangoValidationError) and isinstance(getattr(e, 'message_dict', None), dict):
                for field, errs in e.message_dict.items():
                    for msg in (errs if isinstance(errs, (list, tuple)) else [errs]):
                        form.add_error(field if field in form.fields else None, msg)
                return self.form_invalid(form)
            form.add_error(None, str(e))
            return self.form_invalid(form)
        self.object = pt
        messages.success(self.request, 'Permit type updated successfully')
        return redirect(self.get_success_url())


class StaffVehicleTypeUpdateView(TenantRoleRequiredMixin, FormView):
    allowed_roles = ('admin', 'manager')
    template_name = 'dashboard/staff_vehicle_types.html'
    form_class = StaffVehicleTypeForm

    def dispatch(self, request, *args, **kwargs):
        User = get_user_model()
        self.staff_user = get_object_or_404(User, pk=kwargs.get('user_pk'), tenant=request.tenant, is_super_admin=False)
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        return {
            'vehicle_types': vehicle_type_access_service.get_user_vehicle_types(
                tenant=self.request.tenant,
                user=self.staff_user,
            )
        }

    def form_valid(self, form):
        vehicle_type_access_service.set_user_vehicle_types(
            tenant=self.request.tenant,
            user=self.staff_user,
            vehicle_types=form.cleaned_data.get('vehicle_types'),
            updated_by=self.request.user,
        )
        messages.success(self.request, 'Staff vehicle access updated')
        return redirect('dashboard:staff_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['staff_user'] = self.staff_user
        return ctx
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['staff_user'] = self.staff_user
        return ctx
