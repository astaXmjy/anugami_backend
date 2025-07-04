from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from .models import SystemSetting

class SystemSettingTestCase(TestCase):
    """Tests for System Settings"""

    def setUp(self):
        self.client = APIClient()
        self.system_setting = SystemSetting.objects.create(key="site_name", value="Anugami Store")

    def test_get_system_setting(self):
        response = self.client.get(f"/api/system-settings/{self.system_setting.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_create_system_setting(self):
        data = {"key": "site_logo", "value": "logo.png"}
        response = self.client.post("/api/system-settings/", data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_update_system_setting(self):
        data = {"key": "site_name", "value": "New Store Name"}
        response = self.client.put(f"/api/system-settings/{self.system_setting.id}/", data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
