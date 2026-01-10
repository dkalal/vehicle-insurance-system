from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DetailView, View
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.accounts.permissions import TenantUserRequiredMixin, TenantRoleRequiredMixin
from apps.dynamic_fields.models import FieldDefinition
from apps.dynamic_fields import services as df_services
from .models import Customer, Vehicle, Policy, Payment, SupportRequest
from .forms import CustomerForm, VehicleForm, PolicyForm, PaymentForm, SupportRequestForm
from .services import customer_service, vehicle_service, policy_service, payment_service


class DashboardHomeView(TenantUserRequiredMixin, TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # All managers are tenant-aware; counts are scoped to current tenant
        active_policies = Policy.objects.filter(status=Policy.STATUS_ACTIVE).count()
        vehicles_count = Vehicle.objects.all().count()
        customers_count = Customer.objects.all().count()

        # Expiring soon window (default 30 days; allow tenant override)
        tenant = getattr(self.request, 'tenant', None)
        days = 30
        if tenant:
            try:
                days = int(tenant.get_setting('expiry_reminder_days', 30))
            except Exception:
                days = 30
        today = timezone.now().date()
        soon = today + timedelta(days=days)
        expiring_soon = Policy.objects.filter(
            status=Policy.STATUS_ACTIVE,
            end_date__gt=today,
            end_date__lte=soon,
        ).count()
        expiring_list = Policy.objects.select_related('vehicle', 'vehicle__owner').filter(
            status=Policy.STATUS_ACTIVE,
            end_date__gt=today,
            end_date__lte=soon,
        ).order_by('end_date')[:5]

        ctx.update({
            'metrics': {
                'active_policies': active_policies,
                'expiring_soon': expiring_soon,
                'vehicles': vehicles_count,
                'customers': customers_count,
            },
            'expiring_policies': expiring_list,
        })
        if expiring_soon:
            messages.info(self.request, f"{expiring_soon} policies expiring in next {days} days")
        return ctx


class PolicyDetailView(TenantRoleRequiredMixin, DetailView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Policy
    template_name = 'dashboard/policy_detail.html'
    context_object_name = 'policy'

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
        ctx['df_defs'] = defs
        ctx['df_values'] = values
        return ctx


class PolicyUpdateView(TenantRoleRequiredMixin, UpdateView):
    allowed_roles = ('admin', 'manager')
    model = Policy
    form_class = PolicyForm
    template_name = 'dashboard/policies_form.html'
    success_url = reverse_lazy('dashboard:policies_list')

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

    def form_valid(self, form):
        p = form.save(commit=False)
        p.updated_by = self.request.user
        p.save()
        self.object = p
        values = {}
        defs = FieldDefinition.objects.filter(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_POLICY, is_active=True)
        for df in defs:
            values[df.key] = self.request.POST.get(f"df_{df.key}")
        df_services.bulk_set_by_keys(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_POLICY, obj=p, values=values)
        messages.success(self.request, 'Policy updated')
        return redirect(self.get_success_url())

    def get_initial(self):
        initial = super().get_initial()
        # Default to individual for simpler UX; admins can switch to company
        initial.setdefault('customer_type', 'individual')
        return initial


class CustomerListView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Customer
    template_name = 'dashboard/customers_list.html'
    context_object_name = 'customers'
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Customer.objects
            .only('customer_type', 'first_name', 'last_name', 'company_name', 'email', 'phone', 'created_at')
            .order_by('-created_at')
        )
        q = (self.request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(company_name__icontains=q)
                | Q(email__icontains=q) | Q(phone__icontains=q) | Q(id_number__icontains=q)
            )
        return qs


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

        customer = customer_service.create_customer(
            created_by=self.request.user,
            customer_type=data['customer_type'],
            email=data['email'],
            phone=data['phone'],
            **{k: v for k, v in data.items() if k not in ['customer_type', 'email', 'phone']}
        )
        self.object = customer
        # Save dynamic fields (if provided)
        values = {d.key: self.request.POST.get(f"df_{d.key}") for d in defs}
        df_services.bulk_set_by_keys(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_CUSTOMER, obj=customer, values=values)
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


class CustomerUpdateView(TenantRoleRequiredMixin, UpdateView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Customer
    form_class = CustomerForm
    template_name = 'dashboard/customers_form.html'
    success_url = reverse_lazy('dashboard:customers_list')

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

        customer_service.update_customer(
            updated_by=self.request.user,
            customer=customer,
            **data,
        )
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
        customer = get_object_or_404(Customer, pk=pk)
        customer_service.soft_delete_customer(deleted_by=request.user, customer=customer)
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
        q = (self.request.GET.get('q') or '').strip()
        if q:
            qs = qs.filter(
                Q(registration_number__icontains=q)
                | Q(make__icontains=q) | Q(model__icontains=q)
                | Q(owner__first_name__icontains=q) | Q(owner__last_name__icontains=q) | Q(owner__company_name__icontains=q)
            )
        return qs


class VehicleCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = VehicleForm
    template_name = 'dashboard/vehicles_form.html'
    success_url = reverse_lazy('dashboard:vehicles_list')

    def form_valid(self, form):
        d = form.cleaned_data
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

    def form_valid(self, form):
        v = form.instance
        d = form.cleaned_data
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
        df_services.bulk_set_by_keys(tenant=self.request.tenant, entity_type=FieldDefinition.ENTITY_VEHICLE, obj=v, values=values)
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
        vehicle_service.soft_delete_vehicle(deleted_by=request.user, vehicle=v)
        messages.warning(request, 'Vehicle deleted')
        return redirect(reverse_lazy('dashboard:vehicles_list'))


class PolicyListView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager', 'agent')
    model = Policy
    template_name = 'dashboard/policies_list.html'
    context_object_name = 'policies'
    paginate_by = 25

    def get_queryset(self):
        qs = (
            Policy.objects
            .select_related('vehicle', 'vehicle__owner')
            .only(
                'policy_number', 'status', 'start_date', 'end_date', 'premium_amount',
                'vehicle__registration_number', 'vehicle__make', 'vehicle__model',
                'vehicle__owner__customer_type', 'vehicle__owner__first_name', 'vehicle__owner__last_name', 'vehicle__owner__company_name',
                'created_at'
            )
            .order_by('-created_at')
        )
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


class PolicyCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ('admin', 'manager', 'agent')
    form_class = PolicyForm
    template_name = 'dashboard/policies_form.html'
    success_url = reverse_lazy('dashboard:policies_list')

    def form_valid(self, form):
        d = form.cleaned_data
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
        messages.success(self.request, 'Policy created (pending payment)')
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
        return ctx


class PolicyReportView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ('admin', 'manager')
    model = Policy
    template_name = 'dashboard/policies_report.html'
    context_object_name = 'policies'
    paginate_by = 50

    def get_queryset(self):
        qs = Policy.objects.select_related('vehicle', 'vehicle__owner').order_by('-created_at')
        status = (self.request.GET.get('status') or '').strip()
        if status == 'active':
            qs = qs.filter(status=Policy.STATUS_ACTIVE)
        elif status == 'expired':
            qs = qs.filter(status=Policy.STATUS_EXPIRED)
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
        return SupportRequest.objects.only('subject', 'status', 'priority', 'created_at').order_by('-created_at')


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


class PolicyCancelView(TenantRoleRequiredMixin, View):
    allowed_roles = ('admin', 'manager')

    def post(self, request, pk):
        p = get_object_or_404(Policy, pk=pk)
        reason = (request.POST.get('reason') or '').strip()
        try:
            p.cancel(reason=reason)
            messages.info(request, 'Policy cancelled')
        except Exception as e:
            messages.error(request, str(e))
        return redirect(reverse_lazy('dashboard:policies_list'))


class RegistrationReportView(TenantRoleRequiredMixin, TemplateView):
    allowed_roles = ('admin', 'manager')
    template_name = 'dashboard/registrations_report.html'

    def get_context_data(self, **kwargs):
        from django.db.models.functions import TruncDate, TruncMonth
        ctx = super().get_context_data(**kwargs)
        period = (self.request.GET.get('period') or 'daily').lower()
        grouper = TruncDate('created_at') if period == 'daily' else TruncMonth('created_at')

        customers = (
            Customer.objects
            .annotate(g=grouper)
            .values('g')
            .order_by('g')
            .annotate(count=Count('id'))
        )
        vehicles = (
            Vehicle.objects
            .annotate(g=grouper)
            .values('g')
            .order_by('g')
            .annotate(count=Count('id'))
        )
        policies = (
            Policy.objects
            .annotate(g=grouper)
            .values('g')
            .order_by('g')
            .annotate(count=Count('id'))
        )

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

    def form_valid(self, form):
        d = form.cleaned_data
        pay = payment_service.add_payment_and_activate_policy(
            created_by=self.request.user,
            policy=d['policy'],
            amount=d['amount'],
            payment_method=d['payment_method'],
            reference_number=d['reference_number'],
            payer_name=d.get('payer_name', ''),
            notes=d.get('notes', ''),
        )
        self.object = pay
        messages.success(self.request, 'Payment recorded')
        return redirect(self.get_success_url())

    def get_initial(self):
        initial = super().get_initial()
        policy_id = self.request.GET.get('policy')
        if policy_id:
            try:
                initial['policy'] = Policy.objects.get(pk=int(policy_id))
            except Exception:
                pass
        return initial
