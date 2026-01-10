from django.urls import path
from .views import (
    DashboardHomeView,
    CustomerListView,
    CustomerCreateView,
    CustomerUpdateView,
    CustomerSoftDeleteView,
    VehicleListView,
    VehicleCreateView,
    VehicleUpdateView,
    VehicleSoftDeleteView,
    PolicyListView,
    PolicyCreateView,
    PolicyDetailView,
    PolicyUpdateView,
    PaymentCreateView,
    PolicyReportView,
    RegistrationReportView,
    PolicyCancelView,
    SupportRequestListView,
    SupportRequestCreateView,
)
from apps.dynamic_fields.views import (
    FieldDefinitionListView,
    FieldDefinitionCreateView,
    FieldDefinitionUpdateView,
)

app_name = "dashboard"

urlpatterns = [
    path("", DashboardHomeView.as_view(), name="home"),
    path("customers/", CustomerListView.as_view(), name="customers_list"),
    path("customers/new/", CustomerCreateView.as_view(), name="customers_create"),
    path("customers/<int:pk>/edit/", CustomerUpdateView.as_view(), name="customers_update"),
    path("customers/<int:pk>/delete/", CustomerSoftDeleteView.as_view(), name="customers_delete"),
    path("vehicles/", VehicleListView.as_view(), name="vehicles_list"),
    path("vehicles/new/", VehicleCreateView.as_view(), name="vehicles_create"),
    path("vehicles/<int:pk>/edit/", VehicleUpdateView.as_view(), name="vehicles_update"),
    path("vehicles/<int:pk>/delete/", VehicleSoftDeleteView.as_view(), name="vehicles_delete"),
    path("policies/", PolicyListView.as_view(), name="policies_list"),
    path("policies/new/", PolicyCreateView.as_view(), name="policies_create"),
    path("policies/<int:pk>/", PolicyDetailView.as_view(), name="policies_detail"),
    path("policies/<int:pk>/edit/", PolicyUpdateView.as_view(), name="policies_update"),
    path("policies/<int:pk>/cancel/", PolicyCancelView.as_view(), name="policies_cancel"),
    path("payments/new/", PaymentCreateView.as_view(), name="payments_create"),
    path("policies/report/", PolicyReportView.as_view(), name="policies_report"),
    path("registrations/report/", RegistrationReportView.as_view(), name="registrations_report"),
    path("fields/", FieldDefinitionListView.as_view(), name="fields_list"),
    path("fields/new/", FieldDefinitionCreateView.as_view(), name="fields_create"),
    path("fields/<int:pk>/edit/", FieldDefinitionUpdateView.as_view(), name="fields_update"),
    path("support/", SupportRequestListView.as_view(), name="support_list"),
    path("support/new/", SupportRequestCreateView.as_view(), name="support_create"),
]
