from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .factories import (attach_attribute, create_attribute, create_brand,
                        create_category, create_product)


class CatalogSetUp(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tools = create_category("Tools", "tools")
        self.cement = create_category("Cement", "cement")
        self.bosch = create_brand("Bosch", "bosch")
        self.makita = create_brand("Makita", "makita")

        self.drill = create_product(
            category=self.tools, brand=self.bosch, name="Drill",
            slug="drill", article="A-1", price="100.00", old_price="150.00",
            stock=5, is_featured=True)
        self.saw = create_product(
            category=self.tools, brand=self.makita, name="Circular Saw",
            slug="saw", article="A-2", price="500.00", stock=0)
        self.bag = create_product(
            category=self.cement, name="Cement Bag", slug="cement-bag",
            article="A-3", price="20.00", stock=100)
        self.hidden = create_product(
            category=self.tools, name="Hidden", slug="hidden", article="A-4",
            price="10.00", is_active=False)


class ProductListTests(CatalogSetUp):
    url = "/api/v1/catalog/products/"

    def test_list_is_public_and_excludes_inactive(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = {row["slug"] for row in response.data["results"]}
        self.assertEqual(slugs, {"drill", "saw", "cement-bag"})

    def test_pagination_envelope(self):
        response = self.client.get(self.url)
        for key in ("count", "pages", "next", "previous", "results"):
            self.assertIn(key, response.data)

    def test_search(self):
        response = self.client.get(self.url, {"search": "drill"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "drill")

    def test_category_filter(self):
        response = self.client.get(self.url, {"category": self.cement.pk})
        self.assertEqual(response.data["count"], 1)

    def test_brand_filter(self):
        response = self.client.get(self.url, {"brand": self.bosch.pk})
        self.assertEqual(response.data["count"], 1)

    def test_price_range_filters_compose(self):
        response = self.client.get(
            self.url, {"min_price": "50", "max_price": "200"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["slug"], "drill")

    def test_price_min_max_aliases(self):
        response = self.client.get(
            self.url, {"price_min": "50", "price_max": "200"})
        self.assertEqual(response.data["count"], 1)

    def test_stock_filter(self):
        in_stock = self.client.get(self.url, {"stock": "true"})
        self.assertEqual(
            {r["slug"] for r in in_stock.data["results"]},
            {"drill", "cement-bag"})
        out = self.client.get(self.url, {"stock": "false"})
        self.assertEqual({r["slug"] for r in out.data["results"]}, {"saw"})

    def test_discount_and_featured_filters(self):
        discounted = self.client.get(self.url, {"discount": "true"})
        self.assertEqual({r["slug"] for r in discounted.data["results"]},
                         {"drill"})
        featured = self.client.get(self.url, {"featured": "true"})
        self.assertEqual({r["slug"] for r in featured.data["results"]},
                         {"drill"})

    def test_ordering_by_price(self):
        ascending = self.client.get(self.url, {"ordering": "price"})
        prices = [Decimal(r["price"]) for r in ascending.data["results"]]
        self.assertEqual(prices, sorted(prices))

        descending = self.client.get(self.url, {"ordering": "-price"})
        prices = [Decimal(r["price"]) for r in descending.data["results"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_combined_filters(self):
        response = self.client.get(self.url, {
            "category": self.tools.pk, "min_price": "50",
            "stock": "true", "ordering": "-price"})
        self.assertEqual({r["slug"] for r in response.data["results"]},
                         {"drill"})

    def test_attribute_filter(self):
        attribute, value = create_attribute("power", "Power", "W", "1500")
        attach_attribute(self.drill, attribute, value)
        response = self.client.get(self.url, {"attribute": "power:1500"})
        self.assertEqual({r["slug"] for r in response.data["results"]},
                         {"drill"})

    def test_discount_percent_is_computed(self):
        response = self.client.get(self.url, {"search": "drill"})
        self.assertEqual(response.data["results"][0]["discount_percent"], 33)


class ProductDetailTests(CatalogSetUp):
    def test_detail_by_slug_exposes_full_record(self):
        attribute, value = create_attribute()
        attach_attribute(self.drill, attribute, value)

        response = self.client.get("/api/v1/catalog/products/drill/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ("images", "attributes", "stock", "rating",
                    "review_count", "category", "brand", "old_price"):
            self.assertIn(key, response.data)
        self.assertEqual(len(response.data["attributes"]), 1)
        self.assertEqual(response.data["attributes"][0]["value"], "1500")

    def test_detail_by_id(self):
        response = self.client.get(
            f"/api/v1/catalog/products/{self.drill.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_related_products_share_the_category(self):
        response = self.client.get(
            "/api/v1/catalog/products/drill/related/")
        slugs = {row["slug"] for row in response.data}
        self.assertIn("saw", slugs)
        self.assertNotIn("drill", slugs)
        self.assertNotIn("cement-bag", slugs)

    def test_inactive_product_is_not_retrievable(self):
        response = self.client.get("/api/v1/catalog/products/hidden/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class CategoryBrandTests(CatalogSetUp):
    def test_category_list_reports_product_counts(self):
        response = self.client.get("/api/v1/catalog/categories/")
        counts = {r["slug"]: r["product_count"] for r in
                  response.data["results"]}
        self.assertEqual(counts["tools"], 2)
        self.assertEqual(counts["cement"], 1)

    def test_brand_list_is_public(self):
        response = self.client.get("/api/v1/catalog/brands/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)


class ComparisonTests(CatalogSetUp):
    url = "/api/v1/catalog/products/compare/"

    def test_comparison_returns_products_and_attribute_matrix(self):
        attribute, value = create_attribute("power", "Power", "W", "1500")
        attach_attribute(self.drill, attribute, value)
        other_value = create_attribute("power2", "Power", "W", "2000")[1]
        attach_attribute(self.saw, attribute, value)

        response = self.client.post(
            self.url, {"product_ids": [self.drill.pk, self.saw.pk]},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        self.assertTrue(response.data["attributes"])
        self.assertTrue(response.data["attributes"][0]["is_common"])

    def test_duplicate_ids_rejected(self):
        response = self.client.post(
            self.url, {"product_ids": [self.drill.pk, self.drill.pk]},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_few_products_rejected(self):
        response = self.client.post(
            self.url, {"product_ids": [self.drill.pk]}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_too_many_products_rejected(self):
        ids = [self.drill.pk, self.saw.pk, self.bag.pk, self.hidden.pk,
               self.drill.pk + 100]
        response = self.client.post(self.url, {"product_ids": ids},
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_id_rejected(self):
        response = self.client.post(
            self.url, {"product_ids": [self.drill.pk, 999999]},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_saved_comparison_rejects_mixed_categories(self):
        first = self.client.post(
            f"/api/v1/catalog/compare/{self.drill.pk}/add/")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        mixed = self.client.post(
            f"/api/v1/catalog/compare/{self.bag.pk}/add/")
        self.assertEqual(mixed.status_code, status.HTTP_400_BAD_REQUEST)

    def test_saved_comparison_rejects_duplicates(self):
        self.client.post(f"/api/v1/catalog/compare/{self.drill.pk}/add/")
        again = self.client.post(
            f"/api/v1/catalog/compare/{self.drill.pk}/add/")
        self.assertEqual(again.status_code, status.HTTP_400_BAD_REQUEST)
