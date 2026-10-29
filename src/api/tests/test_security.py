"""Cross-visitor access control: every owner-scoped resource must be
unreachable from another visitor's session."""

from django.conf import settings
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.orders.models import Order

from .factories import auth_client, create_product, create_user, guest_client


class GuestIDORTests(TestCase):
    """Guests are told apart only by their session cookie."""

    def setUp(self):
        self.victim, self.victim_key = guest_client()
        self.attacker, _ = guest_client()
        self.product = create_product()

    def victim_order(self, number="VICTIM-1"):
        return Order.objects.create(
            number=number, session_key=self.victim_key,
            subtotal="10", total="10")

    def test_cannot_read_another_guests_order(self):
        order = self.victim_order()

        detail = self.attacker.get(f"/api/v1/orders/{order.pk}/")
        self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)
        listing = self.attacker.get("/api/v1/orders/")
        self.assertEqual(listing.data["count"], 0)

        self.assertEqual(
            self.victim.get(f"/api/v1/orders/{order.pk}/").status_code,
            status.HTTP_200_OK, "the owner must still see it")

    def test_cannot_cancel_another_guests_order(self):
        order = self.victim_order()
        response = self.attacker.post(f"/api/v1/orders/{order.pk}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        order.refresh_from_db()
        self.assertNotEqual(order.status, Order.Status.CANCELLED)

    def test_a_visitor_without_a_session_owns_no_orders(self):
        # An order with no owner at all (its account was deleted) must not
        # match a visitor whose session key is also missing.
        Order.objects.create(number="ORPHAN-1", subtotal="10", total="10")
        response = APIClient().get("/api/v1/orders/")
        self.assertEqual(response.data["count"], 0)

    def test_an_invented_session_cookie_owns_nothing(self):
        forged = "forgedsessionkey0123456789abcdef"
        order = Order.objects.create(
            number="FORGED-1", session_key=forged, subtotal="10", total="10")
        client = APIClient()
        client.cookies[settings.SESSION_COOKIE_NAME] = forged
        self.assertEqual(
            client.get(f"/api/v1/orders/{order.pk}/").status_code,
            status.HTTP_404_NOT_FOUND)

    def test_cannot_see_another_guests_cart(self):
        self.victim.post("/api/v1/cart/items/",
                         {"product_id": self.product.pk, "quantity": 1},
                         format="json")
        response = self.attacker.get("/api/v1/cart/")
        self.assertEqual(len(response.data["items"]), 0)


# Disabled: the site runs without login and registration.
# class IDORTests(TestCase):
#     def setUp(self):
#         self.victim = create_user(email="victim@example.com")
#         self.attacker = create_user(email="attacker@example.com")
#         self.client = auth_client(APIClient(), self.attacker)
#         self.product = create_product()

#     def test_cannot_read_another_users_order(self):
#         order = Order.objects.create(
#             number="VICTIM-1", user=self.victim, subtotal="10", total="10")

#         detail = self.client.get(f"/api/v1/user/orders/{order.pk}/")
#         self.assertEqual(detail.status_code, status.HTTP_404_NOT_FOUND)

#         listing = self.client.get("/api/v1/user/orders/")
#         self.assertEqual(listing.data["count"], 0)

#     def test_cannot_cancel_another_users_order(self):
#         order = Order.objects.create(
#             number="VICTIM-2", user=self.victim, subtotal="10", total="10")
#         response = self.client.post(f"/api/v1/user/orders/{order.pk}/cancel/")
#         self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
#         order.refresh_from_db()
#         self.assertNotEqual(order.status, Order.Status.CANCELLED)

#     def test_cannot_read_or_modify_another_users_address(self):
#         address = Address.objects.create(
#             user=self.victim, city="Secret", street="S", house="1",
#             phone="+998900000000")

#         self.assertEqual(
#             self.client.get(f"/api/v1/user/addresses/{address.pk}/")
#             .status_code, status.HTTP_404_NOT_FOUND)
#         self.assertEqual(
#             self.client.patch(f"/api/v1/user/addresses/{address.pk}/",
#                               {"city": "Hacked"}, format="json").status_code,
#             status.HTTP_404_NOT_FOUND)
#         self.assertEqual(
#             self.client.delete(f"/api/v1/user/addresses/{address.pk}/")
#             .status_code, status.HTTP_404_NOT_FOUND)

#         address.refresh_from_db()
#         self.assertEqual(address.city, "Secret")

#     def test_cannot_modify_another_users_review(self):
#         mark_purchased(self.victim, self.product)
#         review = Review.objects.create(
#             user=self.victim, product=self.product, author_name="V",
#             rating=5, comment="Victim review", is_published=True)

#         self.assertEqual(
#             self.client.patch(f"/api/v1/user/reviews/{review.pk}/",
#                               {"rating": 1}, format="json").status_code,
#             status.HTTP_404_NOT_FOUND)
#         self.assertEqual(
#             self.client.delete(f"/api/v1/user/reviews/{review.pk}/")
#             .status_code, status.HTTP_404_NOT_FOUND)

#         review.refresh_from_db()
#         self.assertEqual(review.rating, 5)

#     def test_cannot_touch_another_users_wishlist(self):
#         Wishlist.objects.create(user=self.victim, product=self.product)

#         listing = self.client.get("/api/v1/user/wishlist/")
#         self.assertEqual(listing.data["count"], 0)

#         removed = self.client.delete(
#             f"/api/v1/user/wishlist/{self.product.pk}/")
#         self.assertEqual(removed.status_code, status.HTTP_400_BAD_REQUEST)
#         self.assertTrue(
#             Wishlist.objects.filter(user=self.victim).exists())

#     def test_cannot_see_another_users_cart(self):
#         from apps.carts.models import Cart, CartItem
#         cart = Cart.objects.create(user=self.victim)
#         CartItem.objects.create(cart=cart, product=self.product, quantity=2,
#                                 price=self.product.price)

#         response = self.client.get("/api/v1/cart/")
#         self.assertEqual(len(response.data["items"]), 0)


class AdminAccessTests(TestCase):
    def setUp(self):
        self.product = create_product()

    def test_admin_api_rejects_anonymous(self):
        response = APIClient().get("/api/v1/admin/products/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_admin_api_rejects_normal_users(self):
        client = auth_client(APIClient(), create_user(email="n@example.com"))
        self.assertEqual(client.get("/api/v1/admin/products/").status_code,
                         status.HTTP_403_FORBIDDEN)
        self.assertEqual(client.get("/api/v1/admin/orders/").status_code,
                         status.HTTP_403_FORBIDDEN)
        self.assertEqual(client.get("/api/v1/admin/users/").status_code,
                         status.HTTP_403_FORBIDDEN)

    def test_staff_may_access(self):
        staff = create_user(email="staff@example.com", staff=True)
        client = auth_client(APIClient(), staff)
        self.assertEqual(client.get("/api/v1/admin/products/").status_code,
                         status.HTTP_200_OK)

    def test_leads_are_not_publicly_readable(self):
        self.assertEqual(
            APIClient().get("/api/v1/leads/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED)


class PublicEndpointTests(TestCase):
    def test_public_endpoints_need_no_authentication(self):
        create_product()
        client = APIClient()
        for url in ("/api/v1/catalog/products/", "/api/v1/catalog/categories/",
                    "/api/v1/catalog/brands/", "/api/v1/home/",
                    "/api/v1/news/", "/api/v1/promotions/", "/api/v1/faq/",
                    "/api/v1/banners/", "/api/v1/cart/", "/api/v1/orders/",
                    "/healthz/"):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code,
                                 status.HTTP_200_OK)

    # Disabled: the site runs without login and registration.
    # def test_protected_endpoints_require_authentication(self):
    #     client = APIClient()
    #     for url in ("/api/v1/user/profile/", "/api/v1/user/orders/",
    #                 "/api/v1/user/addresses/", "/api/v1/user/wishlist/",
    #                 "/api/v1/user/reviews/"):
    #         with self.subTest(url=url):
    #             self.assertEqual(client.get(url).status_code,
    #                              status.HTTP_401_UNAUTHORIZED)

    def test_account_endpoints_are_gone(self):
        client = APIClient()
        for url in ("/api/v1/auth/login/", "/api/v1/auth/register/",
                    "/api/v1/user/profile/", "/api/v1/user/orders/",
                    "/api/v1/user/addresses/", "/api/v1/user/wishlist/",
                    "/api/v1/user/reviews/"):
            with self.subTest(url=url):
                self.assertEqual(client.post(url).status_code,
                                 status.HTTP_404_NOT_FOUND)
