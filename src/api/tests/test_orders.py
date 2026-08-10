from decimal import Decimal
from unittest import mock

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.catalog.models import Stock
from apps.orders.models import Order
from apps.users.models import Address

from .factories import (auth_client, create_product, create_promo_code,
                        create_user)


class OrderTestBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(email="buyer@example.com")
        auth_client(self.client, self.user)
        self.product = create_product(price="100.00", stock=10)
        self.address = Address.objects.create(
            user=self.user, city="Tashkent", street="Main", house="1",
            phone="+998901234567", is_default=True)

    def fill_cart(self, quantity=2):
        return self.client.post(
            "/api/v1/cart/items/",
            {"product_id": self.product.pk, "quantity": quantity},
            format="json")

    def checkout(self, **overrides):
        payload = {"address_id": self.address.pk, "delivery_type": "delivery",
                   "payment_method": "on_delivery"}
        payload.update(overrides)
        return self.client.post("/api/v1/user/orders/", payload,
                                format="json")


class OrderCreationTests(OrderTestBase):
    def test_checkout_creates_order_with_snapshots(self):
        self.fill_cart(2)
        response = self.checkout()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        order = Order.objects.get(number=response.data["number"])
        item = order.items.get()
        self.assertEqual(item.name_snapshot, self.product.name)
        self.assertEqual(item.article_snapshot, self.product.article)
        self.assertEqual(item.price, Decimal("100.00"))
        self.assertEqual(order.total, Decimal("200.00"))

    def test_snapshots_survive_later_product_changes(self):
        self.fill_cart(1)
        self.checkout()

        self.product.name = "Renamed"
        self.product.price = Decimal("999.00")
        self.product.save(update_fields=["name", "price"])

        order = Order.objects.get(user=self.user)
        item = order.items.get()
        self.assertEqual(item.name_snapshot, "Drill")
        self.assertEqual(item.price, Decimal("100.00"))
        self.assertEqual(order.total, Decimal("100.00"))

    def test_stock_is_decremented(self):
        self.fill_cart(3)
        self.checkout()
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 7)

    def test_cart_is_emptied_after_checkout(self):
        self.fill_cart(1)
        self.checkout()
        cart = self.client.get("/api/v1/cart/")
        self.assertEqual(len(cart.data["items"]), 0)

    def test_empty_cart_cannot_be_checked_out(self):
        response = self.checkout()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_stock_shortfall_blocks_checkout(self):
        self.fill_cart(5)
        Stock.objects.filter(product=self.product).update(quantity=1)

        response = self.checkout()
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 1)

    def test_failure_rolls_the_whole_transaction_back(self):
        """A crash mid-checkout must leave no order and no stock consumed."""
        from apps.carts.services import resolve_cart
        from apps.orders.services import create_order_from_cart

        self.fill_cart(2)
        request = mock.Mock(user=self.user)
        cart = resolve_cart(request)

        with mock.patch("apps.orders.services.OrderItem.objects.bulk_create",
                        side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                create_order_from_cart(
                    user=self.user, cart=cart,
                    address_snapshot=self.address.as_snapshot(),
                    payment_method="on_delivery")

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 10,
                         "stock must not be consumed by a failed checkout")
        self.assertEqual(cart.items.count(), 1,
                         "the cart must survive a failed checkout")

    def test_promo_code_usage_is_counted(self):
        promo = create_promo_code("SAVE10", percent=10)
        self.fill_cart(2)
        self.client.post("/api/v1/cart/promo/", {"code": "SAVE10"},
                         format="json")
        response = self.checkout()

        self.assertEqual(response.data["promo_discount"], "20.00")
        self.assertEqual(response.data["total"], "180.00")
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 1)

    def test_address_snapshot_is_stored(self):
        self.fill_cart(1)
        response = self.checkout()
        self.assertEqual(response.data["address_snapshot"]["city"],
                         "Tashkent")

    def test_delivery_requires_an_address(self):
        self.fill_cart(1)
        response = self.client.post(
            "/api/v1/user/orders/",
            {"delivery_type": "delivery", "payment_method": "card"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_card_payment_starts_awaiting_payment(self):
        self.fill_cart(1)
        response = self.checkout(payment_method="card")
        self.assertEqual(response.data["status"], Order.Status.AWAITING_PAYMENT)


class OrderAccessTests(OrderTestBase):
    def test_list_and_detail_of_own_orders(self):
        self.fill_cart(1)
        created = self.checkout()

        listing = self.client.get("/api/v1/user/orders/")
        self.assertEqual(listing.data["count"], 1)

        detail = self.client.get(f"/api/v1/user/orders/{created.data['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail.data["items"]), 1)

    def test_anonymous_users_are_rejected(self):
        response = APIClient().get("/api/v1/user/orders/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_status_filter(self):
        self.fill_cart(1)
        self.checkout()
        response = self.client.get("/api/v1/user/orders/",
                                   {"status": "processing"})
        self.assertEqual(response.data["count"], 1)

    def test_cancel_restores_stock(self):
        self.fill_cart(2)
        created = self.checkout()
        response = self.client.post(
            f"/api/v1/user/orders/{created.data['id']}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Order.Status.CANCELLED)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 10)

    def test_completed_order_cannot_be_cancelled(self):
        self.fill_cart(1)
        created = self.checkout()
        Order.objects.filter(pk=created.data["id"]).update(
            status=Order.Status.COMPLETED)

        response = self.client.post(
            f"/api/v1/user/orders/{created.data['id']}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
