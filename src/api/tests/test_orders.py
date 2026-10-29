from datetime import timedelta
from decimal import Decimal
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.test import APIClient

from apps.carts.models import Cart
from apps.catalog.models import Stock
from apps.geo.models import City, DeliveryZone, Region
from apps.orders.models import Order
from apps.orders.services import release_expired_orders

from .factories import create_product, create_promo_code

ORDERS = "/api/v1/orders/"

ADDRESS = {"street": "Main", "house": "1"}


class OrderTestBase(TestCase):
    """Guest checkout: the visitor is identified only by the session cookie."""

    def setUp(self):
        self.client = APIClient()
        self.product = create_product(price="100.00", stock=10)
        self.zone = DeliveryZone.objects.create(
            name="City", base_cost=Decimal("15000.00"))
        self.city = City.objects.create(
            region=Region.objects.create(name="Toshkent viloyati"),
            name="Tashkent", delivery_zone=self.zone)

    def fill_cart(self, quantity=2, client=None):
        return (client or self.client).post(
            "/api/v1/cart/items/",
            {"product_id": self.product.pk, "quantity": quantity},
            format="json")

    def checkout(self, client=None, **overrides):
        payload = {"customer_name": "Ali Valiyev",
                   "customer_phone": "+998901234567",
                   "address": ADDRESS, "city_id": self.city.pk,
                   "delivery_type": "delivery",
                   "payment_method": "on_delivery"}
        payload.update(overrides)
        return (client or self.client).post(ORDERS, payload, format="json")


class OrderCreationTests(OrderTestBase):
    def test_guest_can_check_out_without_an_account(self):
        self.fill_cart(2)
        response = self.checkout()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        order = Order.objects.get(number=response.data["number"])
        self.assertIsNone(order.user)
        self.assertTrue(order.session_key)
        self.assertEqual(order.customer_name, "Ali Valiyev")
        self.assertEqual(order.customer_phone, "+998901234567")

    def test_checkout_creates_order_with_snapshots(self):
        self.fill_cart(2)
        response = self.checkout()
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        order = Order.objects.get(number=response.data["number"])
        item = order.items.get()
        self.assertEqual(item.name_snapshot, self.product.name)
        self.assertEqual(item.article_snapshot, self.product.article)
        self.assertEqual(item.price, Decimal("100.00"))
        self.assertEqual(order.total, Decimal("15200.00"))

    def test_snapshots_survive_later_product_changes(self):
        self.fill_cart(1)
        number = self.checkout().data["number"]

        self.product.name = "Renamed"
        self.product.price = Decimal("999.00")
        self.product.save(update_fields=["name", "price"])

        order = Order.objects.get(number=number)
        item = order.items.get()
        self.assertEqual(item.name_snapshot, "Drill")
        self.assertEqual(item.price, Decimal("100.00"))
        self.assertEqual(order.total, Decimal("15100.00"))

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
        from apps.orders.services import create_order_from_cart

        self.fill_cart(2)
        cart = Cart.objects.get(user__isnull=True)

        with mock.patch("apps.orders.services.OrderItem.objects.bulk_create",
                        side_effect=RuntimeError("boom")):
            with self.assertRaises(RuntimeError):
                create_order_from_cart(
                    session_key=cart.session_key, cart=cart,
                    address_snapshot=ADDRESS, city_id=self.city.pk,
                    payment_method="on_delivery")

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 10,
                         "stock must not be consumed by a failed checkout")
        self.assertEqual(cart.items.count(), 1,
                         "the cart must survive a failed checkout")

    def test_order_without_an_owner_is_refused(self):
        from apps.orders.services import create_order_from_cart

        self.fill_cart(1)
        cart = Cart.objects.get(user__isnull=True)
        with self.assertRaises(ValueError):
            create_order_from_cart(cart=cart, address_snapshot=ADDRESS)

    def test_promo_code_usage_is_counted(self):
        promo = create_promo_code("SAVE10", percent=10)
        self.fill_cart(2)
        self.client.post("/api/v1/cart/promo/", {"code": "SAVE10"},
                         format="json")
        response = self.checkout()

        self.assertEqual(response.data["promo_discount"], "20.00")
        self.assertEqual(response.data["total"], "15180.00")
        promo.refresh_from_db()
        self.assertEqual(promo.used_count, 1)

    def test_address_snapshot_is_stored(self):
        self.fill_cart(1)
        response = self.checkout()
        snapshot = response.data["address_snapshot"]
        self.assertEqual(snapshot["city"], "Tashkent")
        self.assertEqual(snapshot["region"], "Toshkent viloyati")
        self.assertEqual(snapshot["street"], "Main")
        self.assertEqual(snapshot["phone"], "+998901234567",
                         "the courier needs the contact phone")

    def test_delivery_requires_an_address(self):
        self.fill_cart(1)
        payload = {"customer_name": "Ali", "customer_phone": "+998901234567",
                   "delivery_type": "delivery", "payment_method": "card"}
        response = self.client.post(ORDERS, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("address", response.data)

    def test_address_needs_a_street(self):
        self.fill_cart(1)
        response = self.checkout(address={"house": "1"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class DeliveryCostTests(OrderTestBase):
    """Delivery is priced by the chosen city's zone and is never free by
    accident."""

    def test_delivery_cost_comes_from_the_city_zone(self):
        self.fill_cart(2)
        response = self.checkout()
        self.assertEqual(response.data["delivery_cost"], "15000.00")
        self.assertEqual(response.data["total"], "15200.00")

    def test_delivery_requires_a_city(self):
        self.fill_cart(1)
        response = self.checkout(city_id=None)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("city_id", response.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_unknown_city_is_refused(self):
        self.fill_cart(1)
        response = self.checkout(city_id=999999)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("city_id", response.data)

    def test_city_without_a_delivery_zone_is_refused(self):
        unpriced = City.objects.create(region=self.city.region, name="Chirchiq")
        self.fill_cart(1)
        response = self.checkout(city_id=unpriced.pk)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("city_id", response.data)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 10)

    def test_free_delivery_needs_a_zone_that_costs_nothing(self):
        free = City.objects.create(
            region=self.city.region, name="Yangiyo'l",
            delivery_zone=DeliveryZone.objects.create(name="Free", base_cost=0))
        self.fill_cart(1)
        response = self.checkout(city_id=free.pk)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["delivery_cost"], "0.00")

    def test_typed_city_cannot_contradict_the_priced_one(self):
        self.fill_cart(1)
        response = self.checkout(address={**ADDRESS, "city": "Samarkand",
                                          "region": "Elsewhere"})
        snapshot = response.data["address_snapshot"]
        self.assertEqual((snapshot["city"], snapshot["region"]),
                         ("Tashkent", "Toshkent viloyati"))

    def test_city_list_shows_only_deliverable_cities_with_prices(self):
        City.objects.create(region=self.city.region, name="Chirchiq")
        response = APIClient().get("/api/v1/geo/cities/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [{
            "id": self.city.pk, "name": "Tashkent",
            "region": "Toshkent viloyati", "delivery_cost": "15000.00"}])

    def test_pickup_needs_no_address(self):
        self.fill_cart(1)
        payload = {"customer_name": "Ali", "customer_phone": "+998901234567",
                   "delivery_type": "pickup", "payment_method": "on_delivery"}
        response = self.client.post(ORDERS, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["address_snapshot"], {})

    def test_contact_details_are_required(self):
        self.fill_cart(1)
        for field in ("customer_name", "customer_phone"):
            with self.subTest(missing=field):
                response = self.checkout(**{field: ""})
                self.assertEqual(response.status_code,
                                 status.HTTP_400_BAD_REQUEST)
                self.assertIn(field, response.data)
        self.assertEqual(Order.objects.count(), 0)

    def test_invalid_phone_is_rejected(self):
        self.fill_cart(1)
        response = self.checkout(customer_phone="12-34")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_card_payment_starts_awaiting_payment(self):
        self.fill_cart(1)
        response = self.checkout(payment_method="card")
        self.assertEqual(response.data["status"], Order.Status.AWAITING_PAYMENT)


class OrderAccessTests(OrderTestBase):
    def test_list_and_detail_of_own_orders(self):
        self.fill_cart(1)
        created = self.checkout()

        listing = self.client.get(ORDERS)
        self.assertEqual(listing.data["count"], 1)

        detail = self.client.get(f"{ORDERS}{created.data['id']}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK)
        self.assertEqual(len(detail.data["items"]), 1)
        self.assertEqual(detail.data["customer_name"], "Ali Valiyev")

    def test_a_new_visitor_has_no_orders(self):
        self.fill_cart(1)
        self.checkout()
        response = APIClient().get(ORDERS)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_status_filter(self):
        self.fill_cart(1)
        self.checkout()
        response = self.client.get(ORDERS, {"status": "processing"})
        self.assertEqual(response.data["count"], 1)

    def test_cancel_restores_stock(self):
        self.fill_cart(2)
        created = self.checkout()
        response = self.client.post(f"{ORDERS}{created.data['id']}/cancel/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], Order.Status.CANCELLED)
        self.assertEqual(Stock.objects.get(product=self.product).quantity, 10)

    def test_completed_order_cannot_be_cancelled(self):
        self.fill_cart(1)
        created = self.checkout()
        Order.objects.filter(pk=created.data["id"]).update(
            status=Order.Status.COMPLETED)

        response = self.client.post(f"{ORDERS}{created.data['id']}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


@override_settings(UNPAID_ORDER_TTL_MINUTES=60)
class UnpaidOrderExpiryTests(OrderTestBase):
    """Card orders left unpaid give their stock back after the TTL."""

    def place(self, payment_method="card", quantity=3):
        self.fill_cart(quantity)
        response = self.checkout(payment_method=payment_method)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return Order.objects.get(number=response.data["number"])

    def age(self, order, minutes):
        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutes))

    def stock(self):
        return Stock.objects.get(product=self.product).quantity

    def test_expired_card_order_is_cancelled_and_restocked(self):
        order = self.place()
        self.assertEqual(self.stock(), 7)
        self.age(order, 61)

        released = release_expired_orders()

        self.assertEqual(released, [order.number])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.stock(), 10)

    def test_order_within_the_ttl_is_kept(self):
        order = self.place()
        self.age(order, 59)
        self.assertEqual(release_expired_orders(), [])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)
        self.assertEqual(self.stock(), 7)

    def test_paid_order_is_kept(self):
        order = self.place()
        Order.objects.filter(pk=order.pk).update(paid_at=timezone.now())
        self.age(order, 120)
        self.assertEqual(release_expired_orders(), [])
        self.assertEqual(self.stock(), 7)

    def test_cash_on_delivery_order_is_kept(self):
        order = self.place(payment_method="on_delivery")
        self.age(order, 600)
        self.assertEqual(release_expired_orders(), [])
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PROCESSING)

    def test_running_twice_restocks_once(self):
        order = self.place()
        self.age(order, 61)
        release_expired_orders()
        self.assertEqual(release_expired_orders(), [])
        self.assertEqual(self.stock(), 10)

    def test_customer_sees_the_payment_deadline(self):
        order = self.place()
        detail = self.client.get(f"{ORDERS}{order.pk}/").data
        due = parse_datetime(detail["payment_due_at"])
        self.assertAlmostEqual(
            (due - order.created_at).total_seconds(), 3600, delta=1)

        cash = self.place(payment_method="on_delivery", quantity=1)
        self.assertIsNone(
            self.client.get(f"{ORDERS}{cash.pk}/").data["payment_due_at"])

    def test_deadline_disappears_once_released(self):
        order = self.place()
        self.age(order, 61)
        release_expired_orders()
        detail = self.client.get(f"{ORDERS}{order.pk}/").data
        self.assertEqual(detail["status"], Order.Status.CANCELLED)
        self.assertIsNone(detail["payment_due_at"])

    def test_management_command(self):
        order = self.place()
        self.age(order, 61)
        out = StringIO()
        call_command("release_expired_orders", stdout=out)
        self.assertIn(order.number, out.getvalue())
        self.assertEqual(self.stock(), 10)

    def test_celery_beat_runs_the_task(self):
        from django.conf import settings

        from apps.orders.tasks import release_expired_orders as task
        from config.celery import app

        scheduled = {job["task"] for job in settings.CELERY_BEAT_SCHEDULE.values()}
        self.assertIn(task.name, scheduled)
        self.assertIn(task.name, app.tasks)

        order = self.place()
        self.age(order, 61)
        self.assertEqual(task.delay().get(), 1)
        self.assertEqual(self.stock(), 10)
