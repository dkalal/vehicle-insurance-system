from django import forms
from .models import Customer, Vehicle, Policy, Payment, SupportRequest


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
        # Sanitize irrelevant fields based on customer_type
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

    def __init__(self, *args, **kwargs):
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
        self.fields['vehicle'].queryset = VehicleModel.objects.select_related('owner').order_by('-created_at')
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
        tailwind_textarea = (
            'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm min-h-24 '
            'focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500'
        )
        self.fields['policy'].widget.attrs.setdefault('class', tailwind_select)
        self.fields['payment_method'].widget.attrs.setdefault('class', tailwind_select)
        # Only show policies that are pending payment to avoid mistakes
        from .models import Policy as PolicyModel
        try:
            pending = PolicyModel.STATUS_PENDING_PAYMENT
            self.fields['policy'].queryset = PolicyModel.objects.filter(status=pending).order_by('-created_at')
        except Exception:
            # Fallback to all tenant policies if constant is unavailable for any reason
            self.fields['policy'].queryset = PolicyModel.objects.all().order_by('-created_at')
        for name, field in self.fields.items():
            if name in ['policy', 'payment_method']:
                continue
            existing = field.widget.attrs.get('class', '')
            if name == 'notes':
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_textarea
            else:
                field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input


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
        # Explicit queryset ordering for owners to surface recent customers
        from .models import Customer as CustomerModel
        self.fields['owner'].queryset = CustomerModel.objects.all().order_by('-created_at')
        for name, field in self.fields.items():
            if name in ['owner', 'vehicle_type', 'notes']:
                continue
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' ' if existing else '') + tailwind_input
        existing_notes = self.fields['notes'].widget.attrs.get('class', '')
        self.fields['notes'].widget.attrs['class'] = (existing_notes + ' ' if existing_notes else '') + tailwind_textarea
