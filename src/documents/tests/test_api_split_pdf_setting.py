from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.test import APITestCase

from paperless.models import ApplicationConfiguration


class TestSplitPdfSetting(APITestCase):
    ENDPOINT = "/api/settings/split_pdf_enabled/"

    def setUp(self) -> None:
        user = User.objects.create_superuser(username="admin")
        self.client.force_authenticate(user=user)

    def test_get_default(self):
        response = self.client.get(self.ENDPOINT, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {"value": False})

    def test_set_value(self):
        response = self.client.put(self.ENDPOINT, {"value": True}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["value"], True)
        config = ApplicationConfiguration.objects.first()
        self.assertTrue(config.split_pdf_enabled)
