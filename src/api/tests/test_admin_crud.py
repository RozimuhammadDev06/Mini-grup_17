"""
End-to-end CRUD over every admin resource.

Each resource is created, read, listed, updated and deleted through the HTTP
API, so a broken serializer or a missing write permission fails loudly rather
than being assumed to work.
"""

import io
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .factories import auth_client, create_category, create_product, create_user

BASE = "/api/v1/admin"


def png_upload(name="test.png"):
    """A real 1x1 PNG — ImageField rejects anything Pillow cannot open."""
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), "white").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(),
                              content_type="image/png")


class AdminCrudTests(TestCase):
    """One test per resource; each walks the full create→delete cycle."""

    def setUp(self):
        self.staff = create_user(email="staff@example.com", staff=True)
        self.client = auth_client(APIClient(), self.staff)
        self.category = create_category("Seed", "seed")

    def assert_crud(self, resource, create_payload, update_payload,
                    update_field, fmt="json"):
        url = f"{BASE}/{resource}/"

        created = self.client.post(url, create_payload, format=fmt)
        self.assertEqual(created.status_code, status.HTTP_201_CREATED,
                         f"CREATE {resource} failed: {created.data}")
        pk = created.data["id"]

        listed = self.client.get(url)
        self.assertEqual(listed.status_code, status.HTTP_200_OK,
                         f"LIST {resource} failed")

        detail = self.client.get(f"{url}{pk}/")
        self.assertEqual(detail.status_code, status.HTTP_200_OK,
                         f"RETRIEVE {resource} failed")

        updated = self.client.patch(f"{url}{pk}/", update_payload,
                                    format="json")
        self.assertEqual(updated.status_code, status.HTTP_200_OK,
                         f"UPDATE {resource} failed: {updated.data}")
        self.assertEqual(str(updated.data[update_field]),
                         str(update_payload[update_field]))

        deleted = self.client.delete(f"{url}{pk}/")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT,
                         f"DELETE {resource} failed")
        self.assertEqual(self.client.get(f"{url}{pk}/").status_code,
                         status.HTTP_404_NOT_FOUND)

    def test_categories(self):
        self.assert_crud(
            "categories",
            {"name": "Power Tools", "slug": "power-tools", "sort": 1,
             "is_active": True},
            {"name": "Renamed"}, "name")

    def test_brands(self):
        self.assert_crud("brands", {"name": "Makita", "slug": "makita"},
                         {"name": "Makita Pro"}, "name")

    def test_products(self):
        self.assert_crud(
            "products",
            {"category": self.category.pk, "name": "Hammer",
             "slug": "hammer", "article": "H-1", "price": "49.99",
             "is_active": True},
            {"price": "59.99"}, "price")

    def test_stock(self):
        product = create_product(category=self.category, slug="stocked",
                                 article="S-1")
        product.stock.delete()
        self.assert_crud(
            "stock",
            {"product": product.pk, "quantity": 10, "status": "in_stock"},
            {"quantity": 3}, "quantity")

    def test_articles(self):
        self.assert_crud(
            "articles",
            {"type": "news", "title": "Launch", "slug": "launch",
             "body": "text", "published_at": timezone.now().isoformat()},
            {"title": "Launch v2"}, "title")

    def test_promotions(self):
        self.assert_crud(
            "promotions",
            {"title": "Spring Sale", "slug": "spring", "body": "text",
             "discount_label": "-20%"},
            {"discount_label": "-30%"}, "discount_label")

    def test_banners(self):
        self.assert_crud("banners",
                         {"title": "Hero", "image": png_upload("hero.png"),
                          "link": "/catalog/", "sort": 1},
                         {"sort": 5}, "sort", fmt="multipart")

    def test_faq(self):
        self.assert_crud("faq",
                         {"question": "Delivery time?", "answer": "2 days",
                          "sort": 1},
                         {"answer": "3 days"}, "answer")

    def test_pages(self):
        self.assert_crud("pages",
                         {"slug": "about", "title": "About", "body": "text"},
                         {"title": "About us"}, "title")

    def test_promo_codes(self):
        self.assert_crud(
            "promo-codes",
            {"code": "SPRING20", "type": "percent", "value": "20.00",
             "min_order": "0.00"},
            {"value": "25.00"}, "value")

    def test_discount_tiers(self):
        self.assert_crud(
            "discount-tiers",
            {"threshold": "1000.00", "percent": 5, "is_active": True},
            {"percent": 7}, "percent")

    def test_reviews(self):
        product = create_product(category=self.category, slug="reviewed",
                                 article="R-1")
        self.assert_crud(
            "reviews",
            {"product": product.pk, "author_name": "Ali", "rating": 5,
             "comment": "Great", "is_published": False},
            {"is_published": True}, "is_published")

    def test_leads(self):
        self.assert_crud(
            "leads",
            {"type": "callback", "name": "Ali", "phone": "+998901234567",
             "consent": True, "status": "new"},
            {"status": "done"}, "status")

    def test_product_images(self):
        product = create_product(category=self.category, slug="imaged",
                                 article="I-1")
        self.assert_crud(
            "product-images",
            {"product": product.pk, "image": png_upload("p.png"), "sort": 1,
             "is_main": True},
            {"sort": 2}, "sort", fmt="multipart")


class AdminRestrictedResourceTests(TestCase):
    """Orders and users are deliberately not fully CRUD-able."""

    def setUp(self):
        self.staff = create_user(email="staff2@example.com", staff=True)
        self.client = auth_client(APIClient(), self.staff)

    def test_orders_cannot_be_created_or_deleted(self):
        from apps.orders.models import Order
        order = Order.objects.create(
            number="ADM-1", user=self.staff, subtotal=Decimal("10"),
            total=Decimal("10"))

        self.assertEqual(self.client.get(f"{BASE}/orders/").status_code,
                         status.HTTP_200_OK)
        self.assertEqual(
            self.client.get(f"{BASE}/orders/{order.pk}/").status_code,
            status.HTTP_200_OK)
        self.assertEqual(
            self.client.post(f"{BASE}/orders/", {}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(
            self.client.delete(f"{BASE}/orders/{order.pk}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_order_status_transition(self):
        from apps.orders.models import Order
        order = Order.objects.create(
            number="ADM-2", user=self.staff, subtotal=Decimal("10"),
            total=Decimal("10"))
        response = self.client.post(
            f"{BASE}/orders/{order.pk}/set-status/", {"status": "shipped"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)

    def test_order_money_is_read_only(self):
        from apps.orders.models import Order
        order = Order.objects.create(
            number="ADM-3", user=self.staff, subtotal=Decimal("10"),
            total=Decimal("10"))
        self.client.patch(f"{BASE}/orders/{order.pk}/",
                          {"total": "0.01"}, format="json")
        order.refresh_from_db()
        self.assertEqual(order.total, Decimal("10"),
                         "order totals must not be editable via the API")

    def test_users_cannot_be_created_or_deleted(self):
        target = create_user(email="target@example.com")
        self.assertEqual(self.client.get(f"{BASE}/users/").status_code,
                         status.HTTP_200_OK)
        self.assertEqual(
            self.client.patch(f"{BASE}/users/{target.pk}/",
                              {"is_active": False},
                              format="json").status_code,
            status.HTTP_200_OK)
        self.assertEqual(
            self.client.post(f"{BASE}/users/", {}, format="json").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(
            self.client.delete(f"{BASE}/users/{target.pk}/").status_code,
            status.HTTP_405_METHOD_NOT_ALLOWED)
