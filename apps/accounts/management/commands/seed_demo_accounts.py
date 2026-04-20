import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.tenants.models import Tenant


def _enabled(value):
    return str(value).strip().lower() not in {"0", "false", "no", "off"}


class Command(BaseCommand):
    help = "Create or update demo login accounts for hosted stakeholder demos."

    def handle(self, *args, **options):
        if not _enabled(os.getenv("BOOTSTRAP_DEMO_ACCOUNTS", "true")):
            self.stdout.write("Demo account bootstrap is disabled.")
            return

        User = get_user_model()

        platform_username = os.getenv("DEMO_PLATFORM_USERNAME", "admin")
        platform_email = os.getenv("DEMO_PLATFORM_EMAIL", "admin@example.com")
        platform_password = os.getenv("DEMO_PLATFORM_PASSWORD", "AdminDemo123!")

        tenant_slug = os.getenv("DEMO_TENANT_SLUG", "demo-insurance")
        tenant_name = os.getenv("DEMO_TENANT_NAME", "Demo Insurance Company")
        tenant_email = os.getenv("DEMO_TENANT_EMAIL", "demo@example.com")

        tenant_username = os.getenv("DEMO_TENANT_USERNAME", "demo_admin")
        tenant_admin_email = os.getenv(
            "DEMO_TENANT_ADMIN_EMAIL", "demo_admin@example.com"
        )
        tenant_password = os.getenv("DEMO_TENANT_PASSWORD", "DemoAdmin123!")

        platform_admin = (
            User.objects.filter(username=platform_username).first()
            or User(username=platform_username)
        )
        platform_admin.email = platform_email
        platform_admin.is_super_admin = True
        platform_admin.is_staff = True
        platform_admin.is_superuser = True
        platform_admin.is_active = True
        platform_admin.tenant = None
        platform_admin.role = None
        platform_admin.must_change_password = False
        platform_admin.set_password(platform_password)
        platform_admin.save()

        tenant, _ = Tenant.objects.get_or_create(
            slug=tenant_slug,
            defaults={
                "name": tenant_name,
                "contact_email": tenant_email,
                "is_active": True,
            },
        )
        tenant.name = tenant_name
        tenant.contact_email = tenant_email
        tenant.is_active = True
        tenant.save()

        tenant_admin = (
            User.objects.filter(username=tenant_username).first()
            or User(username=tenant_username)
        )
        tenant_admin.email = tenant_admin_email
        tenant_admin.tenant = tenant
        tenant_admin.role = User.ROLE_ADMIN
        tenant_admin.is_super_admin = False
        tenant_admin.is_staff = False
        tenant_admin.is_superuser = False
        tenant_admin.is_active = True
        tenant_admin.must_change_password = False
        tenant_admin.set_password(tenant_password)
        tenant_admin.save()

        self.stdout.write(
            self.style.SUCCESS(
                "Demo accounts ready: "
                f"{platform_username} and {tenant_username}"
            )
        )
