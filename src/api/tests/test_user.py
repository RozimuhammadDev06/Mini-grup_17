from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.carts.models import Wishlist
from apps.users.models import Address

from .factories import PASSWORD, auth_client, create_product, create_user


class ProfileTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="p@example.com")
        auth_client(self.client, self.user)

    def test_profile_requires_authentication(self):
        self.assertEqual(
            APIClient().get("/api/v1/user/profile/").status_code,
            status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_profile(self):
        response = self.client.get("/api/v1/user/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], self.user.email)
        self.assertNotIn("password", response.data)

    def test_update_allowed_fields(self):
        response = self.client.patch(
            "/api/v1/user/profile/",
            {"first_name": "Updated", "phone_number": "+998900000000"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Updated")

    def test_privileged_fields_cannot_be_escalated(self):
        response = self.client.patch(
            "/api/v1/user/profile/",
            {"is_staff": True, "is_superuser": True, "is_active": True,
             "email": "attacker@example.com", "first_name": "Ok"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertEqual(self.user.email, "p@example.com")


class ChangePasswordTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="cp@example.com")
        auth_client(self.client, self.user)
        self.url = "/api/v1/user/password/change/"

    def test_change_password_succeeds(self):
        response = self.client.post(
            self.url, {"old_password": PASSWORD, "new_password": "NewPass1!",
                       "new_password2": "NewPass1!"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPass1!"))

    def test_wrong_current_password_rejected(self):
        response = self.client.post(
            self.url, {"old_password": "Nope1!aa",
                       "new_password": "NewPass1!",
                       "new_password2": "NewPass1!"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_new_passwords_must_match(self):
        response = self.client.post(
            self.url, {"old_password": PASSWORD, "new_password": "NewPass1!",
                       "new_password2": "Other1!aa"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_new_password_must_differ(self):
        response = self.client.post(
            self.url, {"old_password": PASSWORD, "new_password": PASSWORD,
                       "new_password2": PASSWORD}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_no_password_material_is_logged(self):
        from apps.users.models import ChangePasswordLogs
        self.client.post(
            self.url, {"old_password": PASSWORD, "new_password": "NewPass1!",
                       "new_password2": "NewPass1!"}, format="json")
        log = ChangePasswordLogs.objects.get(user=self.user)
        self.assertFalse(hasattr(log, "old_password"))
        self.assertFalse(hasattr(log, "new_password"))


class WishlistTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="w@example.com")
        auth_client(self.client, self.user)
        self.product = create_product()

    def test_requires_authentication(self):
        self.assertEqual(
            APIClient().get("/api/v1/user/wishlist/").status_code,
            status.HTTP_401_UNAUTHORIZED)

    def test_add_list_and_remove(self):
        added = self.client.post(
            "/api/v1/user/wishlist/add/", {"product_id": self.product.pk},
            format="json")
        self.assertEqual(added.status_code, status.HTTP_201_CREATED)

        listing = self.client.get("/api/v1/user/wishlist/")
        self.assertEqual(listing.data["count"], 1)

        status_check = self.client.get(
            f"/api/v1/user/wishlist/{self.product.pk}/status/")
        self.assertTrue(status_check.data["in_wishlist"])

        removed = self.client.delete(
            f"/api/v1/user/wishlist/{self.product.pk}/")
        self.assertEqual(removed.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Wishlist.objects.count(), 0)

    def test_duplicates_are_prevented(self):
        payload = {"product_id": self.product.pk}
        self.client.post("/api/v1/user/wishlist/add/", payload, format="json")
        duplicate = self.client.post(
            "/api/v1/user/wishlist/add/", payload, format="json")
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Wishlist.objects.count(), 1)


class AddressTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="a@example.com")
        auth_client(self.client, self.user)
        self.payload = {"city": "Tashkent", "street": "Main", "house": "1",
                        "phone": "+998901112233"}

    def test_crud_cycle(self):
        created = self.client.post("/api/v1/user/addresses/", self.payload,
                                   format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        address_id = created.data["id"]

        listing = self.client.get("/api/v1/user/addresses/")
        self.assertEqual(len(listing.data), 1)

        detail = self.client.get(f"/api/v1/user/addresses/{address_id}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)

        updated = self.client.patch(
            f"/api/v1/user/addresses/{address_id}/", {"city": "Samarkand"},
            format="json")
        self.assertEqual(updated.data["city"], "Samarkand")

        deleted = self.client.delete(
            f"/api/v1/user/addresses/{address_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)

    def test_required_fields_validated(self):
        response = self.client.post("/api/v1/user/addresses/",
                                    {"city": ""}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_cannot_be_spoofed(self):
        victim = create_user(email="victim@example.com")
        response = self.client.post(
            "/api/v1/user/addresses/", {**self.payload, "user": victim.pk},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            Address.objects.get(pk=response.data["id"]).user, self.user)

    def test_only_one_default_address(self):
        first = self.client.post("/api/v1/user/addresses/",
                                 {**self.payload, "is_default": True},
                                 format="json")
        second = self.client.post("/api/v1/user/addresses/",
                                  {**self.payload, "street": "Second"},
                                  format="json")

        promoted = self.client.post(
            f"/api/v1/user/addresses/{second.data['id']}/set-default/")
        self.assertEqual(promoted.status_code, status.HTTP_200_OK)

        defaults = Address.objects.filter(user=self.user, is_default=True)
        self.assertEqual(defaults.count(), 1)
        self.assertEqual(defaults.get().pk, second.data["id"])
