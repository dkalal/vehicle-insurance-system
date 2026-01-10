from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.db import transaction
from apps.accounts.permissions import TenantRoleRequiredMixin
from .models import FieldDefinition
from .forms import FieldDefinitionForm


class FieldDefinitionListView(TenantRoleRequiredMixin, ListView):
    allowed_roles = ("admin",)
    model = FieldDefinition
    template_name = "dashboard/fields_list.html"
    context_object_name = "fields"
    paginate_by = 50

    def get_queryset(self):
        return FieldDefinition.objects.filter(tenant=self.request.tenant).order_by("entity_type", "order", "name")


class FieldDefinitionCreateView(TenantRoleRequiredMixin, CreateView):
    allowed_roles = ("admin",)
    model = FieldDefinition
    form_class = FieldDefinitionForm
    template_name = "dashboard/fields_form.html"
    success_url = reverse_lazy("dashboard:fields_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = getattr(self.request, "tenant", None)
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        from django.db import IntegrityError
        obj = form.save(commit=False)
        obj.tenant = self.request.tenant
        obj.created_by = self.request.user
        obj.updated_by = self.request.user
        try:
            obj.save()
        except IntegrityError:
            form.add_error("key", "A field with this key already exists for this entity")
            return self.form_invalid(form)
        self.object = obj
        return redirect('dashboard:fields_list')


class FieldDefinitionUpdateView(TenantRoleRequiredMixin, UpdateView):
    allowed_roles = ("admin",)
    model = FieldDefinition
    form_class = FieldDefinitionForm
    template_name = "dashboard/fields_form.html"
    success_url = reverse_lazy("dashboard:fields_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["tenant"] = getattr(self.request, "tenant", None)
        return kwargs

    @transaction.atomic
    def form_valid(self, form):
        from django.db import IntegrityError
        obj = form.save(commit=False)
        obj.updated_by = self.request.user
        try:
            obj.save()
        except IntegrityError:
            form.add_error("key", "A field with this key already exists for this entity")
            return self.form_invalid(form)
        self.object = obj
        return redirect('dashboard:fields_list')
