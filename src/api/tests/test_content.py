from datetime import timedelta

from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.content.models import Article, Banner, Faq, Promotion, StaticPage
from apps.leads.models import Lead

from .factories import create_category, create_product


class ContentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        now = timezone.now()
        Article.objects.create(type="news", title="Published", slug="pub",
                               body="x", published_at=now - timedelta(days=1))
        Article.objects.create(type="news", title="Draft", slug="draft",
                               body="x", published_at=None)
        Article.objects.create(type="news", title="Future", slug="future",
                               body="x", published_at=now + timedelta(days=1))

        Promotion.objects.create(title="Live", slug="live",
                                 valid_until=now.date() + timedelta(days=5))
        Promotion.objects.create(title="Expired", slug="expired",
                                 valid_until=now.date() - timedelta(days=1))
        Promotion.objects.create(title="Evergreen", slug="evergreen")

        Banner.objects.create(title="B1", image="b.png", sort=2)
        Banner.objects.create(title="B2", image="b.png", sort=1)
        Faq.objects.create(question="Q?", answer="A", sort=1)
        StaticPage.objects.create(slug="delivery", title="Delivery",
                                  body="Info")

    def test_only_published_articles_are_listed(self):
        response = self.client.get("/api/v1/news/")
        slugs = {row["slug"] for row in response.data["results"]}
        self.assertEqual(slugs, {"pub"})

    def test_unpublished_article_detail_is_404(self):
        self.assertEqual(self.client.get("/api/v1/news/draft/").status_code,
                         status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get("/api/v1/news/pub/").status_code,
                         status.HTTP_200_OK)

    def test_news_search(self):
        response = self.client.get("/api/v1/news/", {"search": "Published"})
        self.assertEqual(response.data["count"], 1)

    def test_expired_promotions_are_excluded(self):
        response = self.client.get("/api/v1/promotions/")
        slugs = {row["slug"] for row in response.data["results"]}
        self.assertEqual(slugs, {"live", "evergreen"})

    def test_banners_are_ordered_by_sort(self):
        response = self.client.get("/api/v1/banners/")
        self.assertEqual([b["title"] for b in response.data], ["B2", "B1"])

    def test_faq_and_static_page(self):
        self.assertEqual(len(self.client.get("/api/v1/faq/").data), 1)
        page = self.client.get("/api/v1/pages/delivery/")
        self.assertEqual(page.data["title"], "Delivery")


class HomeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        category = create_category()
        for i in range(3):
            create_product(category=category, name=f"P{i}", slug=f"p{i}",
                           article=f"ART-{i}", price="100.00",
                           old_price="200.00", is_featured=(i == 0))

    def tearDown(self):
        cache.clear()

    def test_home_returns_every_section(self):
        response = self.client.get("/api/v1/home/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for section in ("banners", "categories", "popular_products",
                        "best_selling_products", "new_products",
                        "discounted_products", "featured_products",
                        "promotions", "news"):
            self.assertIn(section, response.data)

        self.assertEqual(len(response.data["new_products"]), 3)
        self.assertEqual(len(response.data["discounted_products"]), 3)
        self.assertEqual(len(response.data["featured_products"]), 1)

    def test_home_query_count_does_not_scale_with_catalogue_size(self):
        """The real N+1 guard: 10x the products must cost the same queries."""
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as small:
            self.client.get("/api/v1/home/")
        baseline = len(small.captured_queries)

        cache.clear()
        category = create_category()
        for i in range(3, 33):
            create_product(category=category, name=f"P{i}", slug=f"p{i}",
                           article=f"ART-{i}", price="100.00",
                           old_price="200.00")

        with CaptureQueriesContext(connection) as large:
            self.client.get("/api/v1/home/")

        self.assertEqual(len(large.captured_queries), baseline,
                         "home-page queries must be constant, not per-row")

    def test_home_is_cached(self):
        self.client.get("/api/v1/home/")
        with self.assertNumQueries(0):
            response = self.client.get("/api/v1/home/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class LeadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.product = create_product()
        self.payload = {"type": "callback", "name": "Ali",
                        "phone": "+998901234567", "consent": True}

    def test_public_submission(self):
        response = self.client.post("/api/v1/leads/", self.payload,
                                    format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        lead = Lead.objects.get()
        self.assertEqual(lead.status, Lead.Status.NEW)

    def test_consent_is_required(self):
        response = self.client.post(
            "/api/v1/leads/", {**self.payload, "consent": False},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_phone_rejected(self):
        response = self.client.post(
            "/api/v1/leads/", {**self.payload, "phone": "abc"},
            format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_status_cannot_be_set_by_the_submitter(self):
        self.client.post("/api/v1/leads/", {**self.payload, "status": "done"},
                         format="json")
        self.assertEqual(Lead.objects.get().status, Lead.Status.NEW)


class DocsTests(TestCase):
    JSON = "application/vnd.oai.openapi+json"

    def test_every_docs_page_is_reachable(self):
        client = APIClient()
        for url in ("/api/schema/", "/api/docs/", "/api/redoc/",
                    "/api/schema/frontend/", "/api/docs/frontend/",
                    "/api/redoc/frontend/",
                    "/api/schema/admin/", "/api/docs/admin/",
                    "/api/redoc/admin/"):
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code,
                                 status.HTTP_200_OK)

    def _paths(self, url):
        import json
        response = APIClient().get(url, HTTP_ACCEPT=self.JSON)
        return json.loads(response.content)

    def test_frontend_schema_excludes_the_admin_api(self):
        schema = self._paths("/api/schema/frontend/")
        admin_paths = [p for p in schema["paths"] if "/admin/" in p]
        self.assertEqual(admin_paths, [])
        self.assertIn("/api/v1/catalog/products/", schema["paths"])
        self.assertIn("/api/v1/auth/login/", schema["paths"])
        self.assertEqual(schema["info"]["title"],
                         "Stroyopttorg Storefront API")

    def test_admin_schema_contains_only_the_admin_api(self):
        schema = self._paths("/api/schema/admin/")
        non_admin = [p for p in schema["paths"]
                     if "/admin/" not in p and p != "/healthz/"]
        self.assertEqual(non_admin, [])
        self.assertIn("/api/v1/admin/products/", schema["paths"])

    def test_full_schema_is_the_union(self):
        full = set(self._paths("/api/schema/")["paths"])
        frontend = set(self._paths("/api/schema/frontend/")["paths"])
        admin = set(self._paths("/api/schema/admin/")["paths"])
        self.assertEqual(frontend | admin, full,
                         "splitting the docs must not drop any endpoint")

    def test_frontend_schema_documents_jwt_auth(self):
        schema = self._paths("/api/schema/frontend/")
        self.assertIn("jwtAuth", schema["components"]["securitySchemes"])
