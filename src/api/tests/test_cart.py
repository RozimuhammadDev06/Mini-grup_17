from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.carts.models import Cart, CartItem

from .factories import (PASSWORD, auth_client, create_discount_tier,
                        create_product, create_promo_code, create_user)


class CartTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = create_product(price="100.00", stock=5)
        self.other = create_product(
            name="Other", slug="other", article="A-9", price="50.00",
            stock=3)

    def add(self, product=None, quantity=1):
        return self.client.post(
            "/api/v1/cart/items/",
            {"product_id": (product or self.product).pk,
             "quantity": quantity}, format="json")

    def test_guest_can_build_a_cart(self):
        response = self.add(quantity=2)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["totals"]["subtotal"], "200.00")
        self.assertEqual(response.data["totals"]["item_count"], 2)

    def test_price_comes_from_the_database_not_the_request(self):
        self.client.post(
            "/api/v1/cart/items/",
            {"product_id": self.product.pk, "quantity": 1,
             "price": "0.01", "total": "0.01"}, format="json")
        response = self.client.get("/api/v1/cart/")
        self.assertEqual(response.data["totals"]["subtotal"], "100.00")

    def test_adding_more_than_stock_is_rejected(self):
        response = self.add(quantity=99)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("quantity", response.data)

    def test_repeated_adds_accumulate_and_still_respect_stock(self):
        self.add(quantity=3)
        ok = self.add(quantity=2)
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        self.assertEqual(ok.data["totals"]["item_count"], 5)

        too_many = self.add(quantity=1)
        self.assertEqual(too_many.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_quantity(self):
        self.add(quantity=1)
        response = self.client.patch(
            f"/api/v1/cart/items/{self.product.pk}/", {"quantity": 4},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["totals"]["item_count"], 4)

    def test_update_to_zero_removes_the_line(self):
        self.add(quantity=2)
        response = self.client.patch(
            f"/api/v1/cart/items/{self.product.pk}/", {"quantity": 0},
            format="json")
        self.assertEqual(len(response.data["items"]), 0)

    def test_remove_item(self):
        self.add(quantity=1)
        response = self.client.delete(
            f"/api/v1/cart/items/{self.product.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["items"]), 0)

    def test_clear_cart(self):
        self.add(quantity=1)
        self.add(product=self.other, quantity=1)
        response = self.client.delete("/api/v1/cart/")
        self.assertEqual(len(response.data["items"]), 0)

    def test_unknown_product_returns_404(self):
        response = self.client.post(
            "/api/v1/cart/items/", {"product_id": 999999, "quantity": 1},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CartPromoTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = create_product(price="100.00", stock=50)
        self.client.post(
            "/api/v1/cart/items/",
            {"product_id": self.product.pk, "quantity": 2}, format="json")

    def test_percentage_promo_code_reduces_the_total(self):
        create_promo_code("SAVE10", percent=10)
        response = self.client.post(
            "/api/v1/cart/promo/", {"code": "SAVE10"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["totals"]["promo_discount"], "20.00")
        self.assertEqual(response.data["totals"]["total"], "180.00")

    def test_invalid_code_rejected(self):
        response = self.client.post(
            "/api/v1/cart/promo/", {"code": "NOPE"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_minimum_order_is_enforced(self):
        create_promo_code("BIG", percent=50, min_order="1000")
        response = self.client.post(
            "/api/v1/cart/promo/", {"code": "BIG"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exhausted_code_rejected(self):
        promo = create_promo_code("USED", percent=10, usage_limit=1)
        promo.used_count = 1
        promo.save(update_fields=["used_count"])
        response = self.client.post(
            "/api/v1/cart/promo/", {"code": "USED"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_remove_promo_code(self):
        create_promo_code("SAVE10", percent=10)
        self.client.post("/api/v1/cart/promo/", {"code": "SAVE10"},
                         format="json")
        response = self.client.delete("/api/v1/cart/promo/")
        self.assertEqual(response.data["totals"]["promo_discount"], "0.00")

    def test_discount_tier_stacks_before_the_promo_code(self):
        create_discount_tier(threshold="100", percent=10)
        create_promo_code("SAVE10", percent=10)
        response = self.client.post(
            "/api/v1/cart/promo/", {"code": "SAVE10"}, format="json")

        totals = response.data["totals"]
        # 200 subtotal - 10% tier (20) = 180; promo 10% of 180 = 18.
        self.assertEqual(totals["cart_discount"], "20.00")
        self.assertEqual(totals["promo_discount"], "18.00")
        self.assertEqual(totals["total"], "162.00")


class GuestCartMergeTests(TestCase):
    def test_guest_cart_merges_into_the_account_on_login(self):
        client = APIClient()
        product = create_product(price="100.00", stock=10)
        client.post("/api/v1/cart/items/",
                    {"product_id": product.pk, "quantity": 2}, format="json")

        user = create_user(email="merge@example.com")
        Cart.objects.create(user=user)

        response = client.post(
            reverse("auth:login"),
            {"email": user.email, "password": PASSWORD}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user_cart = Cart.objects.get(user=user)
        item = user_cart.items.get(product=product)
        self.assertEqual(item.quantity, 2)
        self.assertFalse(
            Cart.objects.filter(user__isnull=True).exists(),
            "the guest cart should be consumed by the merge")

    def test_merge_clamps_to_available_stock(self):
        client = APIClient()
        product = create_product(price="10.00", stock=3)
        client.post("/api/v1/cart/items/",
                    {"product_id": product.pk, "quantity": 3}, format="json")

        user = create_user(email="clamp@example.com")
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, product=product, quantity=3,
                                price=Decimal("10.00"))

        client.post(reverse("auth:login"),
                    {"email": user.email, "password": PASSWORD},
                    format="json")

        self.assertEqual(cart.items.get(product=product).quantity, 3)
