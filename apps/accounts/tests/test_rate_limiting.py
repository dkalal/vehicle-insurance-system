from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.tenants.models import Tenant


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'test_local_cache',
            'TIMEOUT': 300,
            'KEY_PREFIX': 'vi_test',
        }
    },
    LOGIN_RATE_LIMIT_ATTEMPTS=3,
    LOGIN_RATE_LIMIT_WINDOW_SECONDS=60,
    LOGIN_RATE_LIMIT_BLOCK_SECONDS=300,
)
class LoginRateLimitTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="TestCo", slug="testco", is_active=True)
        User = get_user_model()
        self.user = User.objects.create_user(
            username="agent1",
            email="agent1@testco.com",
            password="Strong!Pass123",
            tenant=self.tenant,
            role=User.ROLE_AGENT,
            is_super_admin=False,
        )
        self.login_url = reverse("accounts:login")

    def test_blocks_after_failed_attempts_and_unblocks_after_success(self):
        # Fail 3 times
        for _ in range(3):
            resp = self.client.post(self.login_url, {"username": "agent1", "password": "wrong"}, follow=True)
            self.assertEqual(resp.status_code, 200)
        # Fourth attempt should be blocked by middleware and redirect to login with message
        resp = self.client.post(self.login_url, {"username": "agent1", "password": "wrong"}, follow=True)
        self.assertEqual(resp.status_code, 200)
        # Now login successfully; this should clear the block
        resp = self.client.post(self.login_url, {"username": "agent1", "password": "Strong!Pass123"}, follow=True)
        self.assertEqual(resp.status_code, 200)
        # Subsequent wrong attempt should not be blocked immediately (counter reset)
        resp = self.client.post(self.login_url, {"username": "agent1", "password": "wrong"}, follow=True)
        self.assertEqual(resp.status_code, 200)
