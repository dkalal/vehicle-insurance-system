from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class NotificationCountTests(TestCase):
    def test_super_admin_receives_zero_count(self):
        user = User.objects.create_user(
            username="sa",
            password="x",
            is_super_admin=True,
        )
        self.client.force_login(user)

        response = self.client.get(reverse("notifications:api_count"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"unread_count": 0})
