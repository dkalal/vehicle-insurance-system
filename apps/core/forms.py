from django import forms
from .models import Customer, Vehicle, Policy, Payment, SupportRequest, LATRARecord, VehiclePermit, PermitType


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            'customer_type',
            # individual
            'first_name', 'last_name', 'id_number', 'date_of_birth',
            # company
            'company_name', 'registration_number', 'tax_id',
            # common
            'email', 'phone', 'address', 'city', 'region', 'postal_code', 'notes',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'address': forms.Textarea(attrs={'rows': 2}),
        }

    def clean(self):
        cleaned = super().clean()
        # Normalize basic string fields
        for f in ['first_name', 'last_name', 'id_number', 'company_name', 'registration_number', 'tax_id', 'email', 'phone', 'city', 'region', 'postal_code']:
            if f in cleaned and isinstance(cleaned.get(f), str):
                cleaned[f] = cleaned[f].strip()
        # Sanitize irrelevant fields based on customer_type only on submission, not when rendering existing data
        ctype = cleaned.get('customer_type')
        if ctype == 'individual':
            # Blank company-only fields to avoid confusion
            for f in ['company_name', 'registration_number', 'tax_id']:
                cleaned[f] = ''
        elif ctype == 'company':
            # Blank individual-only fields
            for f in ['first_name', 'last_name', 'id_number']:
                cleaned[f] = ''
        return cleaned

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add Bootstrap classes
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_textarea = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm min-h-24 '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        select_fields = ['customer_type']
        textarea_fields = ['notes', 'address']
        for name, field in self.fields.items():
            if name in select_fields:
                field.widget.attrs.setdefault('class', tailwind_select)
            elif name in textarea_fields:
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_textarea
            else:
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input


class PolicyForm(forms.ModelForm):
    class Meta:
        model = Policy
        fields = [
            'vehicle', 'start_date', 'end_date', 'premium_amount', 'coverage_amount', 'policy_type', 'notes',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Tenant-aware queryset for vehicles
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_textarea = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm min-h-24 '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        self.fields['vehicle'].widget.attrs.setdefault('class', tailwind_select)
        # Explicit queryset ordering for better UX; manager enforces tenant
        from .models import Vehicle as VehicleModel
        vehicle_qs = VehicleModel.objects.select_related('owner').order_by('-created_at')
        if user is not None:
            from .services import vehicle_access_service
            vehicle_qs = vehicle_access_service.filter_vehicle_queryset_for_user(user=user, queryset=vehicle_qs)
        self.fields['vehicle'].queryset = vehicle_qs
        for name, field in self.fields.items():
            if name in ['vehicle']:
                continue
            existing = field.widget.attrs.get('class', '')
            if name in ['notes']:
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_textarea
            else:
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = [
            'policy', 'amount', 'payment_method', 'reference_number', 'payer_name', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, user=None, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_textarea = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm min-h-24 '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        self.fields['policy'].widget.attrs.setdefault('class', tailwind_select)
        self.fields['payment_method'].widget.attrs.setdefault('class', tailwind_select)
        # Only show policies that are pending payment for this tenant to avoid mistakes
        from .models import Policy as PolicyModel
        try:
            pending = PolicyModel.STATUS_PENDING_PAYMENT
            policy_qs = PolicyModel.objects.filter(status=pending)
        except Exception:
            # Fallback to all policies if constant is unavailable for any reason
            policy_qs = PolicyModel.objects.all()
        if tenant is not None:
            try:
                policy_qs = policy_qs.filter(tenant=tenant)
            except Exception:
                # In this system, policies are tenant-scoped; this branch is defensive only.
                pass
        policy_qs = policy_qs.order_by('-created_at')
        if user is not None:
            from .services import vehicle_access_service
            allowed = vehicle_access_service.get_allowed_vehicle_types_for_user(user)
            if allowed:
                policy_qs = policy_qs.filter(vehicle__vehicle_type__in=allowed)
        self.fields['policy'].queryset = policy_qs
        for name, field in self.fields.items():
            if name in ['policy', 'payment_method']:
                continue
            existing = field.widget.attrs.get('class', '')
            if name == 'notes':
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_textarea
            else:
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input


class PaymentReviewForm(forms.Form):
    ACTION_APPROVE = 'approve'
    ACTION_REJECT = 'reject'

    action = forms.ChoiceField(choices=[
        (ACTION_APPROVE, 'Approve and verify payment'),
        (ACTION_REJECT, 'Reject payment'),
    ])
    review_notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def clean(self):
        cleaned = super().clean()
        action = cleaned.get('action')
        notes = (cleaned.get('review_notes') or '').strip()
        if action == self.ACTION_REJECT and not notes:
            self.add_error('review_notes', 'Please provide a reason when rejecting a payment.')
        cleaned['review_notes'] = notes
        return cleaned


class SupportRequestForm(forms.ModelForm):
    class Meta:
        model = SupportRequest
        fields = [
            'subject', 'message', 'priority',
        ]
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Priority as select for better UX
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_textarea = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm min-h-24 '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        self.fields['priority'].widget = forms.Select(choices=[
            ('low', 'Low'),
            ('normal', 'Normal'),
            ('high', 'High'),
        ], attrs={'class': tailwind_select})
        for name, field in self.fields.items():
            if name == 'priority':
                continue
            existing = field.widget.attrs.get('class', '')
            if name == 'message':
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_textarea
            else:
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = [
            'owner', 'vehicle_type', 'registration_number', 'make', 'model', 'year',
            'color', 'chassis_number', 'engine_number', 'seating_capacity', 'engine_capacity', 'notes',
        ]
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        default_owner = kwargs.pop('default_owner', None)
        super().__init__(*args, **kwargs)
        # Tenant-aware owner queryset is enforced by default manager
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_textarea = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm min-h-24 '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )

        self.fields['owner'].widget.attrs.setdefault('class', tailwind_select)
        self.fields['vehicle_type'].widget.attrs.setdefault('class', tailwind_select)
        if user is not None:
            from .services import vehicle_access_service
            allowed = vehicle_access_service.get_allowed_vehicle_types_for_user(user)
            if allowed:
                self.fields['vehicle_type'].choices = [c for c in self.fields['vehicle_type'].choices if c[0] in allowed]
        # Explicit queryset ordering for owners to surface recent customers
        from .models import Customer as CustomerModel
        self.fields['owner'].queryset = CustomerModel.objects.all().order_by('-created_at')
        if default_owner is not None:
            self.fields['owner'].initial = default_owner
        for name, field in self.fields.items():
            if name in ['owner', 'vehicle_type', 'notes']:
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input
        existing_notes = self.fields['notes'].widget.attrs.get('class', '')
        self.fields['notes'].widget.attrs['class'] = (existing_notes + ' ' if existing_notes else '') + tailwind_textarea


class LATRARecordForm(forms.ModelForm):
    class Meta:
        model = LATRARecord
        fields = [
            'latra_number', 'license_type', 'route', 'start_date', 'end_date',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_textarea = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm min-h-24 '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            existing = field.widget.attrs.get('class', '')
            if name == 'route':
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_textarea
            else:
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input


class VehiclePermitForm(forms.ModelForm):
    class Meta:
        model = VehiclePermit
        fields = [
            'permit_type', 'reference_number', 'start_date', 'end_date', 'document',
        ]
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        self.fields['permit_type'].widget.attrs.setdefault('class', tailwind_select)
        if tenant is not None:
            # Scope permit types to the tenant and active ones only
            self.fields['permit_type'].queryset = PermitType.objects.filter(tenant=tenant, is_active=True).order_by('name')
        for name, field in self.fields.items():
            if name == 'permit_type':
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input


class PermitTypeForm(forms.ModelForm):
    class Meta:
        model = PermitType
        fields = ['name', 'is_active', 'conflicts_with']

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        base = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        if tenant is not None:
            # Only allow conflicts with permit types from the same tenant, excluding self to avoid self-conflict
            qs = PermitType.objects.filter(tenant=tenant).order_by('name')
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            self.fields['conflicts_with'].queryset = qs
        for name, field in self.fields.items():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' ' if existing else '') + base


class CompanyOnboardingForm(forms.Form):
    OPERATION_CHOICES = [
        ('insurance', 'Insurance company'),
        ('fleet', 'Fleet operator'),
        ('broker', 'Broker or agency'),
        ('rental', 'Rental or logistics'),
        ('other', 'Other'),
    ]

    name = forms.CharField(max_length=255)
    contact_email = forms.EmailField()
    contact_phone = forms.CharField(max_length=20, required=False)
    operation_type = forms.ChoiceField(choices=OPERATION_CHOICES, required=False)
    region = forms.CharField(max_length=100, required=False)
    city = forms.CharField(max_length=100, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            if name == 'operation_type':
                field.widget.attrs.setdefault('class', tailwind_select)
            else:
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input


class OrganizationSettingsForm(forms.Form):
    """Tenant organization settings for tenant admins.

    Mirrors the onboarding company form but is safe to use post-onboarding
    and adds organization-level configuration like expiry reminders.
    """

    name = forms.CharField(max_length=255)
    contact_email = forms.EmailField()
    contact_phone = forms.CharField(max_length=20, required=False)
    operation_type = forms.ChoiceField(choices=CompanyOnboardingForm.OPERATION_CHOICES, required=False)
    region = forms.CharField(max_length=100, required=False)
    city = forms.CharField(max_length=100, required=False)
    expiry_reminder_days = forms.IntegerField(min_value=1, max_value=365, required=False,
                                              help_text="How many days before expiry policies should be flagged as expiring soon.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            if name == 'operation_type':
                field.widget.attrs.setdefault('class', tailwind_select)
            else:
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input


class VehicleBasicsOnboardingForm(forms.Form):
    registration_number = forms.CharField(max_length=50)
    vehicle_type = forms.ChoiceField(choices=Vehicle.VEHICLE_TYPE_CHOICES)
    make = forms.CharField(max_length=100)
    model = forms.CharField(max_length=100)
    year = forms.IntegerField()
    color = forms.CharField(max_length=50, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            if name == 'vehicle_type':
                field.widget.attrs.setdefault('class', tailwind_select)
            else:
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input


class OwnerOnboardingForm(forms.Form):
    customer_type = forms.ChoiceField(choices=Customer.CUSTOMER_TYPE_CHOICES)
    first_name = forms.CharField(max_length=100, required=False)
    last_name = forms.CharField(max_length=100, required=False)
    company_name = forms.CharField(max_length=255, required=False)
    email = forms.EmailField()
    phone = forms.CharField(max_length=20)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        tailwind_select = (
            'block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            if name == 'customer_type':
                field.widget.attrs.setdefault('class', tailwind_select)
            else:
                existing = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input

    def clean(self):
        cleaned = super().clean()
        for f in ['first_name', 'last_name', 'company_name', 'email', 'phone']:
            if f in cleaned and isinstance(cleaned.get(f), str):
                cleaned[f] = cleaned[f].strip()
        ctype = cleaned.get('customer_type')
        if ctype == Customer.CUSTOMER_TYPE_INDIVIDUAL:
            cleaned['company_name'] = ''
            if not cleaned.get('first_name') or not cleaned.get('last_name'):
                self.add_error('first_name', 'First and last name are required for individuals.')
        elif ctype == Customer.CUSTOMER_TYPE_COMPANY:
            cleaned['first_name'] = ''
            cleaned['last_name'] = ''
            if not cleaned.get('company_name'):
                self.add_error('company_name', 'Company name is required for company owners.')
        return cleaned


class VehicleBulkImportForm(forms.Form):
    file = forms.FileField(help_text="Upload a CSV file with vehicle details.")

    def clean_file(self):
        f = self.cleaned_data['file']
        if not f.name.lower().endswith('.csv'):
            raise forms.ValidationError('Only CSV files are supported.')
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError('File is too large (max 5MB).')
        return f

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tailwind_input = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        for name, field in self.fields.items():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input
