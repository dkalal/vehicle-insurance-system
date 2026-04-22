from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import Customer, Payment, Policy, Vehicle
from apps.tenants.models import Tenant


User = get_user_model()


class PaymentReviewDisplayTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="JS Logistics", slug="js-logistics", is_active=True)
        self.admin = User.objects.create_user(
            username="tenantadmin",
            email="admin@jslogistics.test",
            password="Pass!12345",
            tenant=self.tenant,
            role=User.ROLE_ADMIN,
        )
        self.customer = Customer.objects.create(
            tenant=self.tenant,
            customer_type=Customer.CUSTOMER_TYPE_COMPANY,
            company_name="JS Logistics",
            phone="+255700000001",
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.vehicle = Vehicle.objects.create(
            tenant=self.tenant,
            owner=self.customer,
            vehicle_type=Vehicle.VEHICLE_TYPE_CAR,
            registration_number="T 999 FFY",
            chassis_number="CHASSIS-999",
            engine_number="ENGINE-999",
            make="Yutong",
            model="D14",
            year=2024,
            created_by=self.admin,
            updated_by=self.admin,
        )
        self.policy = Policy.objects.create(
            tenant=self.tenant,
            policy_number="POL-2026-JS-LOGISTICS-CO-00002",
            vehicle=self.vehicle,
            start_date=timezone.localdate(),
            end_date=timezone.localdate() + timedelta(days=365),
            premium_amount="500000.00",
            status=Policy.STATUS_PENDING_PAYMENT,
            policy_type="Third Party",
            created_by=self.admin,
            updated_by=self.admin,
        )

    def test_review_status_detects_rejected_payment_after_original_notes(self):
        payment = Payment.objects.create(
            tenant=self.tenant,
            policy=self.policy,
            amount="500000.00",
            payment_date=timezone.now(),
            payment_method=Payment.PAYMENT_METHOD_BANK_TRANSFER,
            reference_number="TXN-001",
            payer_name="JS Logistics",
            notes="Original transfer note\n[REJECTED 2026-04-20T20:37:00+03:00 by Admin User] Duplicate transfer reference",
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.assertEqual(payment.review_status, "rejected")
        self.assertEqual(payment.rejection_reason, "Duplicate transfer reference")

    def test_policy_detail_shows_rejection_reason(self):
        Payment.objects.create(
            tenant=self.tenant,
            policy=self.policy,
            amount="500000.00",
            payment_date=timezone.now(),
            payment_method=Payment.PAYMENT_METHOD_BANK_TRANSFER,
            reference_number="TXN-002",
            payer_name="JS Logistics",
            notes="[REJECTED 2026-04-20T20:37:00+03:00 by Admin User] Payment proof does not match the bank reference",
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:policies_detail", args=[self.policy.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rejected")
        self.assertContains(response, "Rejection Reason")
        self.assertContains(response, "Payment proof does not match the bank reference")

    def test_policy_detail_shows_original_recorded_payment_notes(self):
        Payment.objects.create(
            tenant=self.tenant,
            policy=self.policy,
            amount="500000.00",
            payment_date=timezone.now(),
            payment_method=Payment.PAYMENT_METHOD_BANK_TRANSFER,
            reference_number="TXN-002A",
            payer_name="JS Logistics",
            notes="Paid from CRDB branch deposit slip\nCustomer requested same-day activation",
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:policies_detail", args=[self.policy.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recorded Note")
        self.assertContains(response, "Paid from CRDB branch deposit slip")
        self.assertContains(response, "Customer requested same-day activation")

    def test_policy_detail_handles_cancelled_policy_without_actor(self):
        self.policy.status = Policy.STATUS_CANCELLED
        self.policy.cancelled_at = timezone.now()
        self.policy.cancelled_by = None
        self.policy.cancellation_note = "Closed during data cleanup import"
        self.policy.save(update_fields=["status", "cancelled_at", "cancelled_by", "cancellation_note", "updated_at"])

        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:policies_detail", args=[self.policy.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cancelled")
        self.assertContains(response, "Not available")

    def test_fully_paid_pending_policy_is_reconciled_across_policy_views(self):
        Payment.objects.create(
            tenant=self.tenant,
            policy=self.policy,
            amount="500000.00",
            payment_date=timezone.now(),
            payment_method=Payment.PAYMENT_METHOD_BANK_TRANSFER,
            reference_number="TXN-003",
            is_verified=True,
            verified_by=self.admin,
            verified_at=timezone.now(),
            payer_name="JS Logistics",
            created_by=self.admin,
            updated_by=self.admin,
        )

        self.client.force_login(self.admin)

        list_response = self.client.get(reverse("dashboard:policies_list"))
        detail_response = self.client.get(reverse("dashboard:policies_detail", args=[self.policy.pk]))
        report_response = self.client.get(reverse("dashboard:policies_report"))
        vehicle_response = self.client.get(reverse("dashboard:vehicles_detail", args=[self.vehicle.pk]))
        payment_response = self.client.get(reverse("dashboard:payments_create") + f"?policy={self.policy.pk}")

        self.policy.refresh_from_db()

        self.assertEqual(self.policy.status, Policy.STATUS_ACTIVE)
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(report_response.status_code, 200)
        self.assertEqual(vehicle_response.status_code, 200)
        self.assertEqual(payment_response.status_code, 200)

        self.assertContains(list_response, "Active")
        self.assertContains(detail_response, "Active")
        self.assertNotContains(detail_response, "Record Payment")
        self.assertContains(report_response, "Active")
        self.assertContains(vehicle_response, "Active Insurance Coverage")
        self.assertContains(vehicle_response, "Active")
        self.assertNotContains(payment_response, "Pending payment")
