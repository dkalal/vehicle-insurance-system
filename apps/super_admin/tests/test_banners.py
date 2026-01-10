from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from apps.super_admin.models import PlatformConfig

User = get_user_model()


class BannerRenderingTests(TestCase):
    def setUp(self):
        self.sa = User.objects.create_user(username="sa", password="x", is_super_admin=True)
        self.cfg = PlatformConfig.get_solo()

    def test_announcement_banner_renders(self):
        self.cfg.announcement_message = "Planned outage tonight"
        self.cfg.save()

        self.client.force_login(self.sa)
        resp = self.client.get(reverse("super_admin:home"))
        self.assertContains(resp, "Planned outage tonight")

    def test_maintenance_banner_renders_for_super_admin(self):
        self.cfg.maintenance_mode = True
        self.cfg.save()

        self.client.force_login(self.sa)
        resp = self.client.get(reverse("super_admin:home"))
        self.assertContains(resp, "Maintenance mode is enabled.")
