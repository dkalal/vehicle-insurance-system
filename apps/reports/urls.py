from django.urls import path

from .views import (
    ReportsHomeView,
    CustomerPortfolioReportView,
    CustomerPortfolioDetailView,
)


urlpatterns = [
    path("", ReportsHomeView.as_view(), name="reports_home"),
    path("customers/", CustomerPortfolioReportView.as_view(), name="reports_customers"),
    path("customers/<int:pk>/", CustomerPortfolioDetailView.as_view(), name="reports_customer_detail"),
]
