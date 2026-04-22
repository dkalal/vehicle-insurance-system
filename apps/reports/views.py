from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.views.generic import TemplateView

from apps.accounts.permissions import TenantRoleRequiredMixin
from . import services


class ReportsHomeView(TenantRoleRequiredMixin, TemplateView):
    allowed_roles = ("admin", "manager")
    template_name = "dashboard/reports_home.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(
            services.build_reports_home_context(
                tenant=self.request.tenant,
            )
        )
        return ctx


class CustomerPortfolioReportView(TenantRoleRequiredMixin, TemplateView):
    allowed_roles = ("admin", "manager")
    template_name = "dashboard/customer_portfolios_report.html"
    paginate_by = 20

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        report_context = services.build_customer_portfolios_context(
            tenant=self.request.tenant,
            customer_type=self.request.GET.get("customer_type"),
            query=self.request.GET.get("q"),
        )

        paginator = Paginator(report_context["rows"], self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get("page") or 1)
        querydict = self.request.GET.copy()
        querydict.pop("page", None)

        ctx.update(report_context)
        ctx.update(
            {
                "page_obj": page_obj,
                "rows": page_obj.object_list,
                "querystring": querydict.urlencode(),
            }
        )
        return ctx


class CustomerPortfolioDetailView(TenantRoleRequiredMixin, TemplateView):
    allowed_roles = ("admin", "manager")
    template_name = "dashboard/customer_portfolio_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        try:
            ctx.update(
                services.build_customer_portfolio_detail_context(
                    tenant=self.request.tenant,
                    customer_id=kwargs["pk"],
                )
            )
        except Exception as exc:
            raise Http404(str(exc)) from exc
        return ctx

    def render_to_response(self, context, **response_kwargs):
        export = (self.request.GET.get("export") or "").strip().lower()
        if export not in {"csv", "xlsx"}:
            return super().render_to_response(context, **response_kwargs)

        rows = context["vehicle_rows"]
        headers = [
            "Registration Number",
            "Vehicle Type",
            "Make",
            "Model",
            "Year",
            "Compliance",
            "Active Insurance",
            "LATRA",
            "Active Permits",
        ]
        data_rows = [
            [
                row["vehicle"].registration_number,
                row["vehicle"].get_vehicle_type_display(),
                row["vehicle"].make,
                row["vehicle"].model,
                row["vehicle"].year,
                row["compliance"]["status"].replace("_", " ").title(),
                "Yes" if row["snapshot"]["active_insurance"] else "No",
                "Yes" if row["snapshot"]["active_latra"] else "No",
                len(row["snapshot"]["active_permits"]),
            ]
            for row in rows
        ]

        filename_stub = f"customer-portfolio-{context['customer'].pk}"
        if export == "csv":
            import csv

            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="{filename_stub}.csv"'
            writer = csv.writer(response)
            writer.writerow(headers)
            writer.writerows(data_rows)
            return response

        try:
            from io import BytesIO
            from openpyxl import Workbook

            workbook = Workbook()
            sheet = workbook.active
            sheet.title = "Vehicle Register"
            sheet.append(headers)
            for row in data_rows:
                sheet.append(row)

            buffer = BytesIO()
            workbook.save(buffer)
            buffer.seek(0)
            response = HttpResponse(
                buffer.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{filename_stub}.xlsx"'
            return response
        except Exception:
            import csv

            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="{filename_stub}.csv"'
            writer = csv.writer(response)
            writer.writerow(headers)
            writer.writerows(data_rows)
            return response
