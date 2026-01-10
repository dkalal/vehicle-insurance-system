from typing import List
import json

from django import forms

from .models import FieldDefinition


class FieldDefinitionForm(forms.ModelForm):
    """
    UX-friendly options input for dropdowns.
    Accepts:
    - Proper JSON list of strings: ["A", "B"]
    - Comma/newline separated plain text: A, B, C or one-per-line
    - Bracketed unquoted list (legacy): [A, B, C]
    Stores: a normalized Python list of strings.
    """

    # Render textarea for options to accept flexible inputs
    options = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    class Meta:
        model = FieldDefinition
        fields = [
            "entity_type",
            "name",
            "key",
            "data_type",
            "is_required",
            "is_active",
            "order",
            "options",
        ]

    def __init__(self, *args, **kwargs):
        # Accept tenant from view to perform uniqueness validation
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)
        # Add basic classes for consistency
        tw_input = (
            "block w-full rounded-md border border-gray-300 px-3 py-2 text-sm shadow-sm "
            "focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
        )
        tw_select = (
            "block w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm shadow-sm "
            "focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
        )
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault("class", "h-4 w-4 rounded border-gray-300 text-sky-600 focus:ring-sky-500")
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs.setdefault("class", tw_select)
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("class", tw_input + " min-h-24")
            else:
                field.widget.attrs.setdefault("class", tw_input)

        # Helpful hint for options input UX
        self.fields["options"].help_text = (
            "Allowed options for dropdown. Accepts JSON [\"A\",\"B\"], "
            "comma-separated values, or one option per line."
        )

        # Prettier initial rendering for options
        if self.instance and self.instance.pk and isinstance(self.instance.options, list):
            self.initial["options"] = "\n".join(self.instance.options)

    def clean_options(self) -> List[str]:
        data_type = self.cleaned_data.get("data_type") or getattr(self.instance, "data_type", None)
        raw = self.cleaned_data.get("options")

        # Only applicable to dropdown
        if data_type != FieldDefinition.TYPE_DROPDOWN:
            return []

        if raw in (None, "", []):
            return []

        # If a Python list somehow arrives (e.g., from admin), normalize
        if isinstance(raw, list):
            return [str(x).strip() for x in raw if str(x).strip()]

        s = str(raw).strip()

        # Try strict JSON first
        try:
            parsed = json.loads(s)
            if isinstance(parsed, list):
                return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass

        # Accept bracketed unquoted list like: [A, B, C]
        if s.startswith("[") and s.endswith("]"):
            s = s[1:-1]

        # Comma or newline separated values
        parts = []
        for line in s.splitlines():
            parts.extend([p for p in line.split(',')])
        normalized = [p.strip().strip('"\'') for p in parts]
        normalized = [p for p in normalized if p]
        if not normalized:
            return []
        return normalized

    def clean(self):
        cleaned = super().clean()
        # Ensure options only present for dropdown
        if cleaned.get("data_type") != FieldDefinition.TYPE_DROPDOWN:
            cleaned["options"] = []

        # Tenant-scoped uniqueness: (tenant, entity_type, key)
        tenant = self.tenant
        entity = cleaned.get("entity_type")
        key = cleaned.get("key")
        if tenant and entity and key:
            qs = FieldDefinition.objects.filter(tenant=tenant, entity_type=entity, key=key)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error("key", "Key must be unique per entity within your tenant.")
        return cleaned
